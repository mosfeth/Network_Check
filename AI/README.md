# AI - Módulo de Inteligência Artificial
#
# Objetivo: Classificar a qualidade do sinal de rede usando rede neural
#
# ESTRUTURA:
#   __init__.py      → Documentação do módulo e fluxo de aprendizado
#   data.py          → Preparação de dados (features + labels)
#   model.py         → Arquitetura da rede neural (fastAI)
#   predict.py       → Predição para novas medições
#   feedback.py      → Coleta de feedback do operador
#   train.py         → Orquestração do treinamento
#
# DEPENDÊNCIAS:
#   - fastAI (opcional, instalar manualmente)
#   - Supabase (para dados e feedback)
#
# FLUXO DE FUNCIONAMENTO:
#
#   Monitor coleta dados → Supabase (medições)
#        ↓
#   Operador dá feedback → Supabase (machine_feedback)
#        ↓
#   train.py: Medições + Feedback → Dataset → Treino → Modelo
#        ↓
#   predict.py: Novos dados → Modelo → "bom"/"medio"/"ruim"
#        ↓
#   Dashboard mostra previsão + confiança
#        ↓
#   Operador corrige (se necessário) → Feedback → Melhora modelo
#
# GRADUALIDADE:
#   Fase 1: Feedback manual (agora)
#   Fase 2: Modelo sugere, operador confirma (próximo)
#   Fase 3: Autônomo com guarda-chuvas (futuro próximo)
#   Fase 4: Predição de falhas (longo prazo)
#
# PARA INICIAR:
#   1. Instalar fastAI: pip install fastai
#   2. Dar feedback nas máquinas (clicar nos botões no dashboard)
# 3. Executar treinamento: python -m AI.train
#   4. Verificar previsões no dashboard
