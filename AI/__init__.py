# AI/ - Módulo de Inteligência Artificial para classificação de sinal de rede
#
# Este módulo utiliza fastAI para criar uma rede neural que aprende a 
# classificar a qualidade do sinal de rede como:
#   - "bom" (0):  Sinal excelente, adequado para operação crítica
#   - "medio" (1): Sinal aceitável, operação possível com cautela
#   - "ruim" (2): Sinal ruim, risco de falha na operação
#
# FLUXO DE APRENDIZADO GRADUAL:
#
#   Fase 1 (Atual): Operador clica em bom/medio/ruim no card da máquina
#                    → Feedback armazenado no Supabase
#
#   Fase 2 (Próximo): Modelo sugere classificação automaticamente
#                      → Operador confirma ou corrige
#
#   Fase 3 (Futuro): Modelo classifica automaticamente quando confiança > 90%
#                    → Operador só intervém em casos duvidosos
#
#   Fase 4 (Longo prazo): Sistema totalmente autônomo com predição de falhas
#                         → "A rede tende a parar em X minutos"
#
# CADASTRANDO DADOS PARA TREINO:
#
#   A cada medição do monitor + feedback do operador, geramos um dado de treino:
#   {
#       "latency_ms": 25.3,
#       "jitter_ms": 5.1,
#       "packet_loss_percent": 0.0,
#       "packets_received": 100,
#       "packets_sent": 100,
#       "hour_of_day": 14,
#       "day_of_week": 2,
#       "label": "bom"
#   }
#
# Quanto mais dados, melhor o modelo fica.
# A cada ~50 feedbacks, recomenda-se rodar o treinamento (ai/train.py).
#
# DEPENDÊNCIA: fastAI (pip install fastai) - instalar manualmente quando desejar
#              usar a IA. O projeto funciona normalmente sem ela.
