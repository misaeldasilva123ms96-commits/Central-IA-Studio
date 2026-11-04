"""Only compare matching execution profiles; never invent backend timings."""
import math

DEFAULT_SYSTEM_PROMPT = (
    'Você é um assistente de IA. Responda em português brasileiro, a menos que '
    'o usuário peça explicitamente outro idioma. Ao fornecer código, use blocos '
    'Markdown com três crases e indique a linguagem; preserve a indentação.'
)

def backend_timings(value):
    if not isinstance(value,dict):
        return {}
    keys=['prompt_n','prompt_ms','prompt_per_second','predicted_n','predicted_ms','predicted_per_second']
    return {k:v for k in keys if isinstance((v:=value.get(k)),(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0}

def estimate_seconds(previous,model,kind,profile,maximum):
    matching=[s for s in previous if s.get('model')==model and s.get('engine_kind')==kind
              and s.get('profile')==profile and s.get('finish_reason') in ['stop','length']
              and isinstance(s.get('generated_tokens'),int) and s['generated_tokens']>0
              and isinstance(s.get('elapsed'),(int,float)) and s['elapsed']>0]
    if not matching:
        return None,0
    # Weighted end-to-end rate, explicitly labelled as the time for the full budget.
    rate=sum(s['generated_tokens'] for s in matching)/sum(s['elapsed'] for s in matching)
    return maximum/rate,len(matching)
