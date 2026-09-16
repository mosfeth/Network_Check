from supadiag.config import load_settings, ensure_runtime_files
from supadiag.supabase_repository import SupabaseRepository

settings = load_settings()
ensure_runtime_files(settings)
repo = SupabaseRepository(settings)

# Lista máquinas
machines = repo.list_machines(active_only=True)
print('Máquinas ativas:')
for m in machines:
    print(f'  {m.tag} ({m.id}) - Client: {m.client_id}')

# Cria regras de alerta padrão para cada máquina
for m in machines:
    if m.tag == 'INTERNET-CHECK':
        continue  # pula internet check por enquanto
    
    # Regra de latência
    rule_latency = {
        'client_id': m.client_id,
        'machine_id': m.id,
        'name': f'Alerta Latência - {m.tag}',
        'metric': 'latency',
        'condition': 'gte',
        'threshold_warn': 80,
        'threshold_crit': 150,
        'evaluation_window_seconds': 300,
        'cooldown_seconds': 900,
        'enabled': True,
    }
    
    # Regra de perda
    rule_loss = {
        'client_id': m.client_id,
        'machine_id': m.id,
        'name': f'Alerta Perda - {m.tag}',
        'metric': 'loss',
        'condition': 'gte',
        'threshold_warn': 2.0,
        'threshold_crit': 5.0,
        'evaluation_window_seconds': 300,
        'cooldown_seconds': 900,
        'enabled': True,
    }
    
    # Regra de jitter
    rule_jitter = {
        'client_id': m.client_id,
        'machine_id': m.id,
        'name': f'Alerta Jitter - {m.tag}',
        'metric': 'jitter',
        'condition': 'gte',
        'threshold_warn': 30,
        'threshold_crit': 50,
        'evaluation_window_seconds': 300,
        'cooldown_seconds': 900,
        'enabled': True,
    }
    
    for rule in [rule_latency, rule_loss, rule_jitter]:
        rule_id = repo.create_alert_rule(rule)
        print(f'  Criada regra: {rule["name"]} (ID: {rule_id})')

print('Regras criadas!')