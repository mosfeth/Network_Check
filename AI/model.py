# AI/model.py - Definição e treinamento do modelo de rede neural
#
# Este módulo define a arquitetura da rede neural usando fastAI.
#
# ARQUITETURA DA REDE:
#
#   Entrada (7 features)
#       ↓
#   [Dense] 64 neurônios + ReLU + Dropout(0.3)
#       ↓
#   [Dense] 32 neurônios + ReLU + Dropout(0.2)
#       ↓
#   [Dense] 16 neurônios + ReLU + Dropout(0.1)
#       ↓
#   [Dense] 3 neurônios + Softmax  ← Saída (bom, medio, ruim)
#
# EXPLICAÇÃO POR CAMADA:
#
#   Camada Dense (Linear): Cada neurônio recebe todas as entradas,
#   multiplica por pesos, soma e aplica uma função de ativação.
#   É como uma "votação" ponderada de todas as features.
#
#   ReLU (Rectified Linear Unit): Função de ativação que retorna
#   o valor se positivo, senão zero. Ajuda a rede a aprender
#   relações não-lineares (ex: latência alta + perda alta = ruim,
#   mas latência alta sozinha pode ser só medio).
#
#   Dropout: Desliga neurônios aleatoriamente durante o treino
#   (30% no primeiro layer, 20% no segundo, 10% no terceiro).
#   Isso impede "overfitting" (decorar os dados em vez de aprender).
#   É como se a rede tives vários "alunos" estudando juntos,
#   cada um aprendendo coisas diferentes.
#
#   Softmax: Converte os 3 números de saída em probabilidades
#   (soma = 1.0). Exemplo: [0.7, 0.2, 0.1] = 70% bom, 20% medio, 10% ruim.
#
# FUNÇÃO DE PERDA (Loss Function):
#   Usamos CrossEntropyLoss, que mede o erro entre a previsão da rede
#   e a resposta correta. A rede tenta minimizar esse erro ajustando
#   os pesos internamente.
#
# OTIMIZADOR (Adam):
#   Algoritmo que ajusta os pesos da rede. Combina:
#   - Momentum: Acelera em direções consistentes
#   - Taxa de aprendizado adaptativa: Diminui o passo perto do mínimo
#
# EPOCAS E BATCH SIZE:
#   - Épocas: Quantas vezes a rede vê todos os dados. Mais épocas =
#     mais aprendizado, mas risco de overfitting.
#   - Batch Size: Quantos exemplos processar de uma vez. Menor =
#     mais atualizações por época, mas mais lento.
#
# TRANSFER LEARNING (futuro):
#   Quando tiver dados suficientes, podemos treinar um modelo base
#   e reutilizar para novas máquinas (transfer learning).

from __future__ import annotations

try:
    from fastai.tabular.all import *  # type: ignore
    FASTAI_AVAILABLE = True
except ImportError:
    FASTAI_AVAILABLE = False

from typing import Optional, Tuple

# Nome das features (colunas de entrada)
FEATURES = [
    "latency_ms",
    "jitter_ms",
    "packet_loss_percent",
    "packets_received",
    "packets_sent",
    "hour_of_day",
    "day_of_week",
]

# Rótulos possíveis (classes de saída)
LABELS = ["bom", "medio", "ruim"]


def create_model(
    n_features: int = len(FEATURES),
    n_classes: int = len(LABELS),
) -> object:
    """
    Cria a arquitetura da rede neural.

    Retorna um Sequential do PyTorch com a arquitetura descrita:
    7 → 64 → 32 → 16 → 3

    Args:
        n_features: Número de entradas (padrão: 7)
        n_classes: Número de saídas (padrão: 3: bom, medio, ruim)

    Returns:
        Modelo PyTorch pronto para treinamento.

    EXEMPLO:
        >>> model = create_model()
        >>> print(model)
        Sequential(
          (0): Linear(in_features=7, out_features=64, bias=True)
          (1): ReLU()
          (2): Dropout(p=0.3)
          (3): Linear(in_features=64, out_features=32, bias=True)
          (4): ReLU()
          (5): Dropout(p=0.2)
          (6): Linear(in_features=32, out_features=16, bias=True)
          (7): ReLU()
          (8): Dropout(p=0.1)
          (9): Linear(in_features=16, out_features=3, bias=True)
        )
    """
    if not FASTAI_AVAILABLE:
        raise ImportError(
            "fastai não está instalado. "
            "Execute: pip install fastai ou pip install 'supadiag[ai]'"
        )

    # Sequential é o container do PyTorch para camadas sequenciais
    model = nn.Sequential(
        # Camada 1: Entrada → 64 neurônios
        nn.Linear(n_features, 64),
        nn.ReLU(),          # Ativação: libera sinais positivos
        nn.Dropout(0.3),    # Dropout: desliga 30% durante treino

        # Camada 2: 64 → 32 neurônios
        nn.Linear(64, 32),
        nn.ReLU(),
        nn.Dropout(0.2),    # Dropout: desliga 20%

        # Camada 3: 32 → 16 neurônios
        nn.Linear(32, 16),
        nn.ReLU(),
        nn.Dropout(0.1),    # Dropout: desliga 10%

        # Camada 4: 16 → 3 saídas (bom, medio, ruim)
        nn.Linear(16, n_classes),
        # Softmax é aplicado automaticamente pelo CrossEntropyLoss
    )

    return model


def get_learner(
    dls: object,  # DataLoaders do fastAI
    model: Optional[object] = None,
    metrics: Optional[list] = None,
) -> object:
    """
    Cria um Learner do fastAI para treinamento.

    O Learner é o objeto central do fastAI que orquestra:
    - Forward pass (passagem direta)
    - Cálculo da perda
    - Backward pass (cálculo dos gradientes)
    - Atualização dos pesos

    Args:
        dls: DataLoaders (treino + validação)
        model: Modelo pré-criado (opcional, usa arquitetura padrão)
        metrics: Métricas para avaliar (padrão: accuracy)

    Returns:
        Learner do fastAI pronto para .fit()
    """
    if not FASTAI_AVAILABLE:
        raise ImportError("fastai não está instalado.")

    if metrics is None:
        metrics = [accuracy]

    learner = tabular_learner(
        dls,
        layers=[64, 32, 16],  # Camadas ocultas
        n_out=3,               # 3 classes: bom, medio, ruim
        metrics=metrics,
    )

    return learner
