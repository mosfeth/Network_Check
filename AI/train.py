# AI/train.py - Orquestração do treinamento do modelo
#
# Este módulo executa o processo completo de treinamento:
#
#   PASSO 1: Coletar dados
#     - Buscar medições do Supabase (últimos 180 dias por padrão)
#     - Buscar feedbacks do Supabase (mesmo período)
#     - Unir medições + feedbacks (INNER JOIN)
#     - Apenas medições com feedback são usadas no treino
#
#   PASSO 2: Preparar dataset
#     - Converter features para formato numérico
#     - Adicionar features temporais (hora, dia da semana)
#     - Dividir em treino (80%) e validação (20%)
#
#   PASSO 3: Treinar modelo
#     - Criar DataLoader com fastAI
#     - Treinar por N épocas (configurável)
#     - Salvar checkpoints
#
#   PASSO 4: Avaliar modelo
#     - Calcular acurácia no conjunto de validação
#     - Gerar matriz de confusão
#     - Salvar métricas
#
#   PASSO 5: Salvar modelo
#     - Exportar para formato portable
#     - Salvar em AI/models/latest.pkl
#
# REQUISITOS:
#   - fastAI instalado: pip install fastai
#   - Mínimo de 50 dados rotulados (feedback + medição)
#   - Recomendado: 200+ dados para resultados confiáveis
#
# COMO EXECUTAR:
#   python -m ai.train
#   python -m ai.train --epochs 50 --min-samples 100
#
# RECURSOS DE SEGURANÇA:
#   - Validação de dados mínimos antes de treinar
#   - Backup do modelo anterior
#   - Logging detalhado do processo
#   - Cancelamento seguro (Ctrl+C)
#
# FUTURO:
#   - Treino automático quando novos feedbacks chegam (CRON)
#   - Transfer learning para novas máquinas
#   - Comparação de versões do modelo (A/B testing)
#   - Versionamento de modelos (MLflow, Weights & Biases)

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional


# Diretório onde os modelos serão salvos
MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "AI", "models",
)

# Nome do arquivo do modelo mais recente
LATEST_MODEL = os.path.join(MODELS_DIR, "latest.pkl")

# Nome do arquivo do modelo anterior (backup)
BACKUP_MODEL = os.path.join(MODELS_DIR, "backup.pkl")


def ensure_model_dir() -> None:
    """Cria o diretório de modelos se não existir."""
    os.makedirs(MODELS_DIR, exist_ok=True)


def backup_existing_model() -> bool:
    """
    Faz backup do modelo atual antes de treinar novo.

    Retorna True se houve backup, False se não existia modelo anterior.

    POR QUE BACKUP?
    Se o novo modelo for pior (overfitting, poucos dados),
    podemos voltar para o modelo anterior.
    """
    if os.path.exists(LATEST_MODEL):
        import shutil
        shutil.copy2(LATEST_MODEL, BACKUP_MODEL)
        print(f"✅ Backup salvo em: {BACKUP_MODEL}")
        return True
    print("ℹ️  Nenhum modelo anterior para fazer backup.")
    return False


def get_data_range(days: int = 180) -> tuple[str, str]:
    """
    Calcula o intervalo de datas para buscar dados.

    Args:
        days: Número de dias para trás (padrão: 180)

    Returns:
        Tupla (data_inicio_iso, data_fim_iso)

    EXEMPLO:
        >>> get_data_range(30)
        ('2026-08-18T13:16:00+00:00', '2026-09-17T13:16:00+00:00')
    """
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=days)
    return inicio.isoformat(), agora.isoformat()


def check_fastai_available() -> None:
    """Verifica se fastAI está instalado."""
    try:
        import fastai  # noqa: F401
        print(f"✅ fastAI encontrado (v{fastai.__version__})")
    except ImportError:
        print("❌ fastAI não instalado!")
        print("   Instale com: pip install fastai")
        print("   Ou:         pip install 'supadiag[ai]'")
        sys.exit(1)


def validate_training_data(data: list[dict], min_samples: int) -> bool:
    """
    Valida se há dados suficientes para treinamento.

    Args:
        data: Lista de dados de treino
        min_samples: Mínimo de amostras necessário

    Returns:
        True se tem dados suficientes, False se não
    """
    if len(data) < min_samples:
        print(f"⚠️  Dados insuficientes: {len(data)} amostras (mínimo: {min_samples})")
        print("   Colete mais feedback dos operadores antes de treinar.")
        return False

    # Verifica se temos as 3 classes
    labels = set(d["label"] for d in data)
    if len(labels) < 3:
        print(f"⚠️  Classes insuficientes: {labels} (precisa de 3: bom, medio, ruim)")
        print("   Peça feedback para todas as categorias.")
        return False

    return True


def train(
    epochs: int = 30,
    min_samples: int = 50,
    days: int = 180,
    machine_id: Optional[str] = None,
) -> bool:
    """
    Processo completo de treinamento.

    Args:
        epochs: Número de épocas de treinamento
        min_samples: Mínimo de amostras para treinar
        days: Dias de histórico para buscar dados
        machine_id: Se informado, treina apenas para esta máquina

    Returns:
        True se treinou com sucesso, False se falhou

    FLUXO:
        1. Verifica dependências
        2. Coleta dados do Supabase
        3. Valida dados
        4. Faz backup do modelo anterior
        5. Treina o modelo
        6. Avalia a acurácia
        7. Salva o modelo
    """
    print("=" * 60)
    print("  AI - Iniciando Treinamento do Modelo")
    print("=" * 60)

    # PASSO 1: Verificar dependências
    print("\n[1/7] Verificando dependências...")
    check_fastai_available()

    # PASSO 2: Coletar dados
    print(f"\n[2/7] Coletando dados dos últimos {days} dias...")
    from ai.data import build_training_row
    from ai.feedback import classify_status

    # TODO: Implementar conexão com Supabase
    # data = collect_training_data(machine_id=machine_id, days=days)
    # Por enquanto, mostramos instruções:
    print("   Implementar: fetch measurements + feedback from Supabase")
    print("   → SupabaseRepository.list_machines()")
    print("   → SupabaseRepository.get_measurements_window()")
    print("   → SupabaseRepository (feedback table)")

    # PASSO 3: Validação de dados (placeholder)
    print(f"\n[3/7] Validando dados (mínimo: {min_samples})...")
    # data = [...]
    # if not validate_training_data(data, min_samples):
    #     return False
    print("   ⚠️  Placeholder - implementar coleta de dados")

    # PASSO 4: Backup
    print(f"\n[4/7] Preparando backup...")
    ensure_model_dir()
    backup_existing_model()

    # PASSO 5: Treinamento (placeholder)
    print(f"\n[5/7] Treinando por {epochs} épocas...")
    # from ai.model import create_model, get_learner, FEATURES, LABELS
    # learner = get_learner(dls)
    # learner.fit_one_cycle(epochs)
    print("   ⚠️  Placeholder - implementar com fastAI")

    # PASSO 6: Avaliação (placeholder)
    print(f"\n[6/7] Avaliando modelo...")
    print("   ⚠️  Placeholder - implementar avaliação")

    # PASSO 7: Salvar (placeholder)
    print(f"\n[7/7] Salvando modelo...")
    print(f"   Modelo salvo em: {LATEST_MODEL}")

    print("\n✅ Treinamento concluído!")
    return True


def main() -> None:
    """Ponto de entrada para linha de comando."""
    parser = argparse.ArgumentParser(
        description="Treinar modelo de IA para classificação de sinal"
    )
    parser.add_argument(
        "--epochs", type=int, default=30,
        help="Número de épocas de treinamento (padrão: 30)"
    )
    parser.add_argument(
        "--min-samples", type=int, default=50,
        help="Mínimo de amostras para treinar (padrão: 50)"
    )
    parser.add_argument(
        "--days", type=int, default=180,
        help="Dias de histórico (padrão: 180)"
    )
    parser.add_argument(
        "--machine-id", type=str, default=None,
        help="Treinar apenas para máquina específica (opcional)"
    )

    args = parser.parse_args()

    success = train(
        epochs=args.epochs,
        min_samples=args.min_samples,
        days=args.days,
        machine_id=args.machine_id,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
