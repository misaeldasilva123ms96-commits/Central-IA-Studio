"""Gera pesos aleatórios determinísticos para teste estrutural, sem modelo baixado.
Não é um modelo treinado e não produz respostas úteis.
Uso: python make_tiny_gguf.py /caminho/llama.cpp destino.gguf
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'gguf-py'))
import gguf
import numpy as np

path=Path(sys.argv[2]);path.parent.mkdir(parents=True,exist_ok=True)
w=gguf.GGUFWriter(path,'llama')
w.add_name('Central Engine random test fixture — NOT TRAINED')
w.add_context_length(4096);w.add_embedding_length(64);w.add_block_count(1)
w.add_feed_forward_length(128);w.add_head_count(2);w.add_head_count_kv(2)
w.add_rope_dimension_count(32);w.add_layer_norm_rms_eps(1e-5)
w.add_tokenizer_model('llama')
tokens=['<unk>','<s>','</s>','▁']+[f'<0x{i:02X}>' for i in range(256)]
w.add_token_list(tokens);w.add_token_scores([0.0]*len(tokens));w.add_token_types([2,3,3,1]+[6]*256)
w.add_bos_token_id(1);w.add_eos_token_id(2);w.add_unk_token_id(0)
w.add_add_bos_token(True)
w.add_chat_template("{% if enable_thinking is defined and enable_thinking %}think: {% endif %}{% for message in messages %}{{ message['role'] + ': ' + message['content'] + '\\n' }}{% endfor %}{% if add_generation_prompt %}assistant: {% endif %}")
rng=np.random.default_rng(1234)
shapes={'token_embd.weight':(260,64),'output_norm.weight':(64,),'output.weight':(260,64),
 'blk.0.attn_norm.weight':(64,),'blk.0.ffn_norm.weight':(64,),
 'blk.0.attn_q.weight':(64,64),'blk.0.attn_k.weight':(64,64),'blk.0.attn_v.weight':(64,64),
 'blk.0.attn_output.weight':(64,64),'blk.0.ffn_gate.weight':(128,64),
 'blk.0.ffn_up.weight':(128,64),'blk.0.ffn_down.weight':(64,128)}
for name,shape in shapes.items():
 data=np.ones(shape,dtype=np.float32) if len(shape)==1 else rng.normal(0,.02,shape).astype(np.float32)
 w.add_tensor(name,data)
w.write_header_to_file();w.write_kv_data_to_file();w.write_tensors_to_file();w.close()
print(f'Fixture aleatória criada: {path.stat().st_size} bytes; sem dados de treinamento.')
