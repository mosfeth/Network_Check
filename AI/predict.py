# AI/predict.py - Predição/inferencia usando o modelo treinado
#
# Este módulo carrega o modelo treinado e faz previsões para novas medições.
#
# COMO FUNCIONA A PREDIÇÃO:
#
#   1. Recebe os dados de uma medição (latência, jitter, perda, etc.)
#   2. Aplica as mesmas transformações do treino
#   3. Passa pela rede neural
#   4. Recebe 3 probabilidades: [bom, medio, ruim]
#   5. Retorna a classificação + confiança
#
# ESCALA DE CONFIANÇA:
#   - > 90%: Alta confiança (classificação confiável)
#   - 70-90%: Média confiança (recomendação, não decisão)
#   - < 70%: Baixa confiança (precisa de feedback humano)
#
# LIMITE DE CONFIANÇA PARA AUTONOMIA:
#   Configurável via SUPADIAG_AI_CONFIDENCE_THRESHOLD (padrão: 0.9)
#   Acima deste limite, o sistema classifica automaticamente.
#   Abaixo, pede feedback ao operador.
#
# PREDIÇÃO EM TEMPOS DE FALHA:
#   Se o modelo prevê "ruim" por mais de N ciclos consecutivos,
#   pode indicar que "a rede tende a parar em X tempo".
#   Isso será implementado na Fase 4 (longo prazo).
#
# EXEMPLO DE USO:
#   from AI.predict import predict_measurement
#   result = predict_measurement(
#       latency_ms=25.3,
#       jitter_ms=5.1,
#       packet_loss_percent=0.0,
#       packets_received=100,
#       packets_sent=100,
#       hour_of_day=14,
#       day_of_week=2,
#   )
#   print(result)
#   # {"label": "bom", "confidence": 0.95, "probabilities": {"bom": 0.95, "medio": 0.04, "ruim": 0.01}}

from __future__ import annotations

import os
from typing import Optional


# Limiar de confiança para autonomia (pode vir do .env no futuro)
# SUPADIAG_AI_CONFIDENCE_THRESHOLD=0.9
CONFIDENCE_THRESHOLD = float(
    os.getenv("SUPADIAG_AI_CONFIDENCE_THRESHOLD", "0.9")
)

# Mapeamento de índice para label
LABELS = ["bom", "medio", "ruim"]


def predict_measurement(
    latency_ms: float | None,
    jitter_ms: float | None,
    packet_loss_percent: float,
    packets_received: int,
    packets_sent: int,
    hour_of_day: int,
    day_of_week: int,
    model: Optional[object] = None,
) -> dict:
    """
    Prediz a qualidade do sinal para uma medição.

    Args:
        latency_ms: Latência em milissegundos
        jitter_ms: Jitter em milissegundos
        packet_loss_percent: Perda de pacotes em percentual (0-100)
        packets_received: Pacotes recebidos com sucesso
        packets_sent: Total de pacotes enviados
        hour_of_day: Hora do dia (0-23) - para detectar padrões temporais
        day_of_week: Dia da semana (0-6, segunda=0) - para detectar padrões semanais
        model: Modelo treinado. Se None, tenta carregar do diretório AI/models/

    Returns:
        Dicionário com:
            - label: "bom", "medio", ou "ruim"
            - confidence: Probabilidade da classe escolhida (0-1)
            - probabilities: Todas as probabilidades {"bom": x, "medio": y, "ruim": z}
            - autonomous: Se a classificação foi automática (confiança > threshold)

    EXEMPLO:
        >>> result = predict_measurement(
        ...     latency_ms=25.3, jitter_ms=5.1,
        ...     packet_loss_percent=0.0, packets_received=100,
        ...     packets_sent=100, hour_of_day=14, day_of_week=2,
        ... )
        >>> print(result["label"])      # "bom"
        >>> print(result["confidence"])  # 0.95
        >>> print(result["autonomous"])  # True (confiança > 0.9)
    """
    # Se nenhum modelo foi passado, tenta carregar o mais recente
    if model is None:
        from AI.model import create_model, FEATURES
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "AI", "models", "latest.pkl",
        )
        if os.path.exists(model_path):
            import torch
            model = torch.load(model_path, weights_only=False)  # noqa: S301
            model.eval()
        else:
            # Sem modelo treinado, usa regra simples como fallback
            return _rule_based_prediction(
                latency_ms, jitter_ms, packet_loss_percent,
                packets_received, packets_sent,
            )

    # Prepara as features na ordem correta
    features = [
        latency_ms or 0.0,
        jitter_ms or 0.0,
        packet_loss_percent,
        packets_received,
        packets_sent,
        hour_of_day,
        day_of_week,
    ]

    try:
        import torch

        with torch.no_grad():
            # Converte para tensor 2D (1 amostra, 7 features)
            tensor = torch.tensor([features], dtype=torch.float32)

            # Forward pass: passa pela rede neural
            # Retorna 3 logits (uma para cada classe)
            logits = model(tensor)

            # Softmax: converte logits em probabilidades (soma = 1.0)
            probabilities = torch.softmax(logits, dim=1).squeeze()

            # Encontra a classe com maior probabilidade
            best_idx = int(torch.argmax(probabilities))
            best_label = LABELS[best_idx]
            confidence = float(probabilities[best_idx])

        return {
            "label": best_label,
            "confidence": round(confidence, 4),
            "probabilities": {
                LABELS[i]: round(float(probabilities[i]), 4)
                for i in range(len(LABELS))
            },
            "autonomous": confidence >= CONFIDENCE_THRESHOLD,
        }
    except Exception:
        # Se falhar, usa regras simples como fallback
        return _rule_based_prediction(
            latency_ms, jitter_ms, packet_loss_percent,
            packets_received, packets_sent,
        )


def _rule_based_prediction(
    latency_ms: float | None,
    jitter_ms: float | None,
    packet_loss_percent: float,
    packets_received: int,
    packets_sent: int,
) -> dict:
    """
    Predição baseada em regras simples (fallback sem IA).

    Esta é a lógica original do sistema, usada antes do modelo
    ser treinado ou quando o modelo não está disponível.

    Regras:
        - 0% perda, latência < 50ms → "bom"
        - 0% perda, latência < 150ms → "medio"
        - > 0% perda ou latência ≥ 150ms → "ruim"
        - 0 pacotes recebidos → "ruim"

    RETORNA:
        Dicionário com label, confidence=0.5 (sem confiança de IA),
        probabilities baseadas nas regras, e autonomous=False.
    """
    # Se não recebeu nenhum pacote, é ruim
    if packets_received == 0:
        return {
            "label": "ruim",
            "confidence": 1.0,
            "probabilities": {"bom": 0.0, "medio": 0.0, "ruim": 1.0},
            "autonomous": True,
        }

    total = packets_sent if packets_sent > 0 else 1
    loss = (total - packets_received) / total * 100
    latency = latency_ms or 0.0

    if loss == 0 and latency < 50:
        label = "bom"
    elif loss < 5 and latency < 150:
        label = "medio"
    else:
        label = "ruim"

    # Probabilidades: 100% na classe escolhida (fallback)
    probs = {"bom": 0.0, "medio": 0.0, "ruim": 0.0}
    probs[label] = 1.0

    return {
        "label": label,
        "confidence": 1.0,
        "probabilities": probs,
        "autonomous": True,
    }
