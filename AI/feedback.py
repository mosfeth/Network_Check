# AI/feedback.py - Coleta e armazenamento de feedback do operador
#
# Este módulo gerencia o feedback humano que alimenta o modelo de IA.
#
# POR QUE FEEDBACK HUMANO É IMPORTANTE?
#   - A rede neural precisa de exemplos rotulados para aprender
#   - O operador conhece o contexto que os sensores não conhecem
#     (ex: "estamos em manutenção programada", "é feriado")
#   - Feedback corrige erros do modelo gradualmente
#
# TIPOS DE FEEDBACK:
#   - "bom" (0):     Rede está operando normalmente, sem preocupações
#   - "medio" (1):   Rede funcionando, mas com ressalvas
#                     (ex: latência alta mas estável)
#   - "ruim" (2):    Rede com problemas graves
#                     (ex: perda de pacotes alta, indisponibilidade)
#
# COMO O FEEDBACK É STORED:
#   Cada feedback é armazenado no Supabase na tabela machine_feedback,
#   vinculado a uma medição específica. Isso cria o par (input → label)
#   necessário para o treino.
#
# GRADUALIDADE (Fases de autonomia):
#
#   Fase 1 - OPERADOR COMTCTA TUDO:
#     Três botões no card: 🟢 Bom, 🟡 Médio, 🔴 Ruim
#     Operador clica um botão por ciclo de medição.
#
#   Fase 2 - MODELO SUGERE:
#     Modelo mostra sua previsão no card
#     Operador confirma (👍) ou corrige (👎)
#     Feedback corrige o modelo mais rápido.
#
#   Fase 3 - AUTÔNOMO COM GUARDA-CHUVAS:
#     Modelo classifica automaticamente (confiança > 90%)
#     Operador só intervém quando modelo pede (confiança < 70%)
#     Sistema alerta: "Sugiro classificar como ruim, confirmar?"
#
#   Fase 4 - PREDIÇÃO DE FALHAS:
#     Modelo detecta padrões que precedem falhas
#     Alerta: "A rede tende a parar em 30 minutos"
#     Operador pode tomar ação preventiva
#
# BOAS PRÁTICAS DE FEEDBACK:
#   - Dar feedback pelo menos 1x por hora durante as primeiras semanas
#   - Corrigir o modelo imediatamente quando errar
#   - Adicionar notas contextuais (implementar no futuro)
#   - Revisar o modelo mensalmente com novos dados

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .data import hour_of_day, day_of_week


def classify_status(
    latency_ms: float | None,
    jitter_ms: float | None,
    packet_loss_percent: float,
    packets_received: int,
    packets_sent: int,
) -> str:
    """
    Classifica a medição usando regras simples (fallback e validação).

    Esta função é a mesma lógica usada em icmp.py para classificação
    baseada em pacotes, mas também considera latência.

    Regras de classificação:
    - "bom":    100% pacotes recebidos E latência < 150ms
    - "medio":  Pacotes recebidos E (latência ≥ 150ms OU perda > 0%)
    - "ruim":   Sem pacotes recebidos OU perda > 50%

    Args:
        latency_ms: Latência em ms
        jitter_ms: Jitter em ms (não usado na classificação, mas recebido para consistência)
        packet_loss_percent: Percentual de perda (0-100)
        packets_received: Pacotes recebidos
        packets_sent: Total de pacotes enviados

    Returns:
        "bom", "medio", ou "ruim"
    """
    if packets_received == 0:
        return "ruim"

    # Calcular perda real baseada em pacotes (mais confiável que packet_loss_percent)
    total = packets_sent if packets_sent > 0 else 1
    actual_loss = (total - packets_received) / total * 100

    # Bom: sem perda e latência aceitável
    if actual_loss == 0 and (latency_ms or 0) < 150:
        return "bom"

    # Médio: alguma perda ou latência elevada, mas ainda operável
    if actual_loss < 50 and (latency_ms or 0) < 500:
        return "medio"

    # Ruim: alta perda ou latência extrema
    return "ruim"


def prepare_feedback_data(
    machine_id: str,
    label: str,
    latency_ms: Optional[float],
    jitter_ms: Optional[float],
    packet_loss_percent: float,
    packets_received: int,
    packets_sent: int,
    measured_at: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Prepara dados de feedback para armazenamento.

    Args:
        machine_id: ID da máquina no Supabase
        label: Feedback do operador ("bom", "medio", "ruim")
        latency_ms: Latência em milissegundos
        jitter_ms: Jitter em milissegundos
        packet_loss_percent: Perda de pacotes (%)
        packets_received: Pacotes recebidos
        packets_sent: Pacotes enviados
        measured_at: Timestamp da medição (padrão: agora)
        notes: Notas opcionais do operador (ex: "manutenção programada")

    Returns:
        Dicionário pronto para inserir no banco de dados

    EXEMPLO:
        >>> data = prepare_feedback_data(
        ...     machine_id="abc-123",
        ...     label="medio",
        ...     latency_ms=85.0,
        ...     jitter_ms=15.0,
        ...     packet_loss_percent=2.5,
        ...     packets_received=97,
        ...     packets_sent=100,
        ...     notes="Latência elevada mas estável"
        ... )
    """
    if measured_at is None:
        measured_at = datetime.now(timezone.utc).isoformat()

    # Valida o label
    if label not in ("bom", "medio", "ruim"):
        raise ValueError(f"Label inválido: {label}. Use 'bom', 'medio' ou 'ruim'.")

    return {
        "machine_id": machine_id,
        "label": label,
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
        "packet_loss_percent": packet_loss_percent,
        "packets_received": packets_received,
        "packets_sent": packets_sent,
        "hour_of_day": hour_of_day(measured_at),
        "day_of_week": day_of_week(measured_at),
        "notes": notes,
        "created_at": measured_at,
    }
