# Roadmap do Projeto NVRBox

Este arquivo e o backlog unico do projeto. Quando uma tarefa for concluida, remova ou atualize a entrada correspondente para evitar informacao duplicada ou desatualizada.

## Prioridade alta

Nenhum item critico aberto no momento.

## Prioridade media

- Tratar melhor erros de leitura de `cameras.local.json`.
  - Escrita atomica ja e usada.
  - Falta exibir erro claro no painel quando o JSON local estiver invalido.

- Validar melhor a selecao de armazenamento em ambientes Android.
  - Confirmar caminhos reais usados por TV Box e smartphones.
  - Tratar permissao negada de forma clara no painel.

## Prioridade baixa

- Melhorar mensagens no painel para:
  - falha no live stream;
  - disco perto do limite.

- Tentar perfis RTSP conhecidos em sequencia quando o usuario nao souber o modelo.

- Melhorar compatibilidade geral com dispositivos moveis.

## Melhorias futuras

- Criar uma tela de configuracoes do sistema.
  - Tempo de cada segmento.
  - Limite de limpeza do disco.
  - Transporte RTSP padrao.
  - Preferencias de exibicao.

- Melhorar a organizacao do backend.
  - Separar regras de validacao e funcoes do painel em modulos menores.
  - Manter `servidor.py` focado nas rotas Flask.

- Gerenciar processos com `systemd`.
  - Servico para painel.
  - Servico para captura.
  - Servico para limpeza.
  - Restart automatico em caso de falha.

- Adicionar edicao de cameras cadastradas.
  - Alterar nome.
  - Alterar URL RTSP.
  - Alterar MAC.
  - Alterar protocolo UDP/TCP.

- Mostrar status detalhado por camera.
  - Online/offline.
  - Ultima gravacao.
  - Quantidade de videos.
  - Tamanho ocupado em disco.
  - PID do processo FFmpeg.

- Adicionar controle de captura por camera.
  - Pausar captura.
  - Retomar captura.
  - Reiniciar processo FFmpeg.

- Melhorar busca e filtros de gravacoes.
  - Filtrar por camera.
  - Filtrar por intervalo de horario.
  - Manter filtro por data.

- Adicionar exclusao manual de gravacoes pelo painel.

- Adicionar download em lote de gravacoes.

- Adicionar migracao manual de gravacoes entre armazenamentos.
  - Copiar videos antigos para a memoria nova.
  - Confirmar espaco disponivel antes da copia.

- Criar indicador de saude do sistema.
  - Uso de disco.
  - Quantidade de cameras online.
  - Status dos processos.
  - Ultimo erro registrado.

- Adicionar backup, importacao e exportacao de `cameras.local.json`.

- Criar recuperacao assistida de gravacoes antigas invalidas.
  - Tentar remux com FFmpeg quando um `.mp4` antigo perdeu indice final.
  - Manter arquivo original preservado durante a tentativa.
