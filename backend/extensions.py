"""Bundled extension catalog and persisted installation state; never downloads code."""

PLUGINS=[
 ('web','Pesquisa na internet','Busca pública e leitura de páginas. Requer Internet ativada.','Pesquisa',['web_search','web_fetch'],True),
 ('documents','Leitura de documentos','Consulta trechos e busca em documentos anexados à conversa.','Documentos',['read_attachment','search_attachment'],True),
 ('workspace','Arquivos do projeto','Lista, lê e edita arquivos conforme o modo e suas permissões.','Desenvolvimento',['list_files','read_file','write_file'],True),
 ('terminal','Terminal do projeto','Executa programas no Build, seguindo o nível de aprovação escolhido.','Desenvolvimento',['run_command'],True),
 ('calculator','Calculadora','Calcula expressões aritméticas localmente, sem executar código.','Produtividade',['calculate'],False),
 ('json','Assistente JSON','Valida e formata JSON, com diagnóstico de erro.','Desenvolvimento',['format_json'],False),
 ('csv','Análise de CSV','Resume uma coluna numérica, com opção de excluir negativos.','Dados',['summarize_csv'],False),
 ('clock','Data e hora','Consulta a data e a hora atuais em UTC no computador.','Produtividade',['current_datetime'],False),
]
SKILLS=[
 ('code-review','Revisão de código','Revisar problemas concretos e sugerir correções.','Desenvolvimento','Revise o código procurando defeitos concretos. Cite trechos e explique o impacto. Sugira uma correção mínima e como verificar. Não invente execução de testes.'),
 ('python','Programação Python','Apoio para escrever e explicar código Python.','Desenvolvimento','Ajude a programar em Python com soluções claras, validação de entradas e tratamento de erros adequado. Explique dependências e como executar; não afirme ter executado sem resultado real de ferramenta.'),
 ('planning','Planejamento de projetos','Transformar um objetivo em etapas verificáveis.','Produtividade','Transforme o objetivo em etapas com entregas, dependências e critérios de conclusão. Diferencie fatos de suposições. Respeite Plan e as permissões do aplicativo.'),
 ('writing','Redação e revisão','Melhorar clareza e organização de textos.','Escrita','Revise e redija em português brasileiro, com linguagem clara. Preserve o sentido, os nomes e os fatos fornecidos. Não invente informações para preencher lacunas.'),
 ('summary','Resumo de documentos','Organizar os pontos principais dos anexos.','Documentos','Resuma os documentos em pontos principais, decisões e pendências. Use as ferramentas de anexos para consultar trechos necessários. Informe quando não houver acesso ao conteúdo completo.'),
 ('data-analysis','Análise de dados','Explicar cálculos e resultados com atenção a limites.','Dados','Analise dados com atenção a valores ausentes, duplicados, unidades e negativos. Explicite filtros e suposições. Use ferramentas de cálculo quando disponíveis e não invente resultados.'),
 ('translation','Tradução','Traduzir preservando sentido e formatação.','Escrita','Traduza para o idioma pedido preservando sentido, nomes, números e formatação. Se não houver idioma de destino, pergunte. Não traduza identificadores de código sem pedido.'),
 ('research','Pesquisa com fontes','Pesquisar e comparar informações com URLs.','Pesquisa','Quando a pergunta exigir informação atual, use ferramentas web se disponíveis. Cite URLs realmente consultadas, compare fontes e indique incertezas. Sem Internet, não afirme ter pesquisado.'),
]


def catalog(store):
    state=store.get('extensions',{})
    result=[]
    for key,name,description,category,tools,default in PLUGINS:
        saved=state.get(key,{'installed':default,'enabled':default})
        result.append(dict(id=key,name=name,description=description,category=category,kind='plugin',tools=tools,version='1.0.0',author='Central IA',bundled=True,**saved))
    for key,name,description,category,prompt in SKILLS:
        saved=state.get(key,{'installed':False,'enabled':False})
        result.append(dict(id=key,name=name,description=description,category=category,kind='skill',instructions=prompt,tools=[],version='1.0.0',author='Central IA',bundled=True,**saved))
    return result


def change(store,key,action):
    item=next((i for i in catalog(store) if i['id']==key),None)
    if not item:raise ValueError('Extensão não encontrada.')
    if action=='install':status={'installed':True,'enabled':True}
    elif action=='remove':status={'installed':False,'enabled':False}
    elif action in ['enable','disable']:
        if not item['installed']:raise ValueError('Instale a extensão primeiro.')
        status={'installed':True,'enabled':action=='enable'}
    else:raise ValueError('Ação desconhecida.')
    state=store.get('extensions',{});state[key]=status;store.put('extensions',state)
    return catalog(store)


def tools_for(store,definitions):
    active={name for item in catalog(store) if item['kind']=='plugin' and item['installed'] and item['enabled'] for name in item['tools']}
    return [t for t in definitions if t['function']['name'] in active]


def apply_skills(store,messages,ids):
    selected=[];available={i['id']:i for i in catalog(store) if i['kind']=='skill'}
    for key in dict.fromkeys(ids):
        item=available.get(key)
        if not item or not item['installed'] or not item['enabled']:raise ValueError('Habilidade não instalada ou desativada: '+key)
        selected.append(item['name']+': '+item['instructions'])
    if not selected:return messages
    messages=[dict(m) for m in messages];text='Habilidades selecionadas para auxiliar esta tarefa; respeite o pedido do usuário e as permissões:\n'+'\n'.join(selected)
    if messages and messages[0]['role']=='system':messages[0]['content']+='\n\n'+text
    else:messages.insert(0,{'role':'system','content':text})
    return messages
