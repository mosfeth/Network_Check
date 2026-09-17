# AI/data.py - Preparação de dados para o modelo de IA
#
# Este módulo é responsável por:
#   1. Buscar medições históricas do Supabase
#   2. Buscar feedbacks do operador
#   3. Unir medições + feedbacks em um dataset de treino
#   4. Adicionar features temporais (hora, dia da semana)
#
# CONCEITO DE FEATURES (entradas da rede neural):
#
#   A rede neural recebe números como entrada. Precisamos converter
#   os dados reais em números que a rede entenda:
#
#   Feature                  | Tipo    | Exemplo
#   -------------------------|---------|--------
#   latency_ms               | float   | 25.3 (milissegundos)
#   jitter_ms                | float   | 5.1 (variação em ms)
#   packet_loss_percent      | float   | 0.0 (0-100)
#   packets_received         | int     | 100 (quantidade)
#   packets_sent             | int     | 100 (quantidade)
#   hour_of_day              | int     | 14 (0-23, hora do dia)
#   day_of_week              | int     | 2 (0-6, segunda=0, domingo=6)
#
#   LABEL (o que a rede deve aprender a prever):
#   label                    | Classe  | Exemplo
#   -------------------------|---------|--------
#   label                    | str     | "bom", "medio", ou "ruim"
#
# POR QUE INCLUIR HORA E DIA DA SEMANA?
#   Redes neurais aprendem padrões. Incluindo hora e dia, o modelo pode
#   aprender que:
#   - Às 3h da manhã o sinal é pior (menos tráfego, rotas diferentes)
#   - Segundas-feiras têm mais problemas (retorno de fim de semana)
#   - Horários de pico (9h-12h, 14h-18h) têm mais perda
#
# NORMALIZAÇÃO:
#   fastAI cuida da normalização automaticamente. Mas é importante
#   entender que valores grandes (como 1000ms de latência) e pequenos
#   (como 0.01% de perda) precisam ser tratados juntos.
#   fastAI usa BatchNorm e WeightNorm internamente.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def hour_of_day(measured_at: str) -> int:
    """Extrai a hora (0-23) de um timestamp ISO."""
    try:
        dt = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
        return dt.hour
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).hour


def day_of_week(measured_at: str) -> int:
    """Extrai o dia da semana (0=segunda, 6=domingo) de um timestamp ISO."""
    try:
        dt = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
        return dt.weekday()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).weekday()


def build_training_row(measurement: dict, feedback_label: str) -> dict:
    """
    Constrói uma linha de treino a partir de uma medição e seu feedback.

    Args:
        measurement: Dicionário com dados da medição do Supabase.
            Espera: latency_ms, jitter_ms, packet_loss_percent,
                    packets_sent, packets_received, measured_at
        feedback_label: Etiqueta do operador ("bom", "medio", "ruim")

    Returns:
        Dicionário com features numéricas + label para o modelo.

    EXEMPLO:
        >>> build_training_row(
        ...     {"latency_ms": 25.3, "jitter_ms": 5.1, "packet_loss_percent": 0.0,
        ...      "packets_sent": 100, "packets_received": 100, "measured_at": "2026-09-17T14:30:00+00:00"},
        ...     "bom"
        ... )
        {
            "latency_ms": 25.3,
            "jitter_ms": 5.1,
            "packet_loss_percent": 0.0,
            "packets_received": 100,
            "packets_sent": 100,
            "hour_of_day": 14,
            "day_of_week": 2,
            "label": "bom"
        }
    """
    return {
        "latency_ms": measurement.get("latency_ms") or 0.0,
        "jitter_ms": measurement.get("jitter_ms") or 0.0,
        "packet_loss_percent": measurement.get("packet_loss_percent") or 0.0,
        "packets_received": measurement.get("packets_received") or 0,
        "packets_sent": measurement.get("packets_sent") or 0,
        "hour_of_day": hour_of_day(measurement.get("measured_at", "")),
        "day_of_week": day_of_week(measurement.get("measured_at", "")),
        "label": feedback_label,
    }
