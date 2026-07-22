# Melhorias do Projeto NVRBox

Este arquivo e o controle unico das melhorias planejadas. Quando uma tarefa for concluida, marque a caixa correspondente com `[x]` e ajuste a descricao se o comportamento final mudar.

## Foco atual

Manter o NVRBox leve, local e robusto para rodar em:

- PC Linux.
- TV Box ou mini PC ARM.
- Android via Termux.

O sistema continua sem tela de login por enquanto, pois o uso previsto e em rede local confiavel. Docker fica para uma etapa futura, depois de validar bem o funcionamento em PC, ARM e Termux.

## Prioridade alta

- [x] Corrigir a reproducao de videos ja gravados.
  - Tentar tocar primeiro o `.mp4` original salvo na pasta.
  - Usar `/video_compativel/<arquivo>` somente como fallback.
  - Evitar que o video salvo pareca um stream que vai carregando aos poucos.
  - Mostrar a duracao completa obtida por `ffprobe`.
  - Manter cache em memoria para metadados dos videos; cache persistente de WebM fica para depois se o fallback ainda pesar em hardware fraco.

- [x] Criar tela de mosaico para ver todas as cameras ao vivo.
  - Adicionar botao `Ver todas` no painel principal.
  - Mostrar grade responsiva com todas as cameras.
  - Exibir nome e status em cada camera.
  - Clicar em uma camera deve abrir a tela individual.
  - Adicionar pausa/retomada geral para fechar os streams quando o mosaico nao estiver em uso.

- [x] Adicionar exclusao manual de gravacoes.
  - Apagar um video especifico.
  - Apagar todos os videos de uma camera.
  - Usar somente rotas `POST`.
  - Exigir confirmacao antes de apagar.
  - Permitir apagar apenas arquivos `.mp4` dentro da pasta de gravacoes ativa.
  - Para apagar todos de uma camera, limitar aos arquivos que comecam com o slug da camera e preservar arquivos recentes ou em gravacao.

- [x] Reforcar e testar a limpeza automatica.
  - Confirmar que apaga quando o disco passa do limite configurado.
  - Confirmar que o padrao de 90% funciona.
  - Confirmar que remove primeiro os videos mais antigos.
  - Confirmar que preserva videos novos e segmentos em gravacao.
  - Garantir que a limpeza so atua dentro da pasta de gravacoes ativa.
  - Garantir que a limpeza so apaga arquivos `.mp4`.
  - Registrar em log claro o que foi apagado e cobrir o comportamento com testes automatizados.

- [ ] Criar calendario interativo de gravacoes.
  - Mostrar dias com gravacoes.
  - Mostrar dias sem gravacoes.
  - Exibir quantidade de videos por dia.
  - Permitir clicar no dia para filtrar a lista.
  - Manter filtro por data simples como fallback.

- [ ] Permitir escolher o tempo dos segmentos pelo painel.
  - Opcoes iniciais: 5, 10 e 15 minutos.
  - Salvar escolha em `sistema.json`.
  - Fazer `captura.py` detectar alteracao e reiniciar FFmpeg para aplicar o novo tempo.
  - Manter variavel `NVRBOX_TEMPO_SEGMENTO` como override opcional.

- [ ] Melhorar o status real das cameras.
  - Hoje o status online testa apenas a porta RTSP.
  - Diferenciar porta aberta, RTSP valido, senha/perfil incorreto, timeout e camera sem video.
  - Usar `ffprobe` com timeout curto e cache para nao pesar no painel.

- [ ] Validar gravacoes sem deixar o painel pesado.
  - A API leve nao deve marcar todo `.mp4` como reproduzivel sem checar.
  - Criar cache simples de validacao por arquivo.
  - Revalidar apenas videos novos ou modificados.
  - Separar arquivos validos e invalidos de forma confiavel.

## Prioridade media

- [ ] Melhorar confiabilidade do RTSP.
  - Manter UDP/TCP por camera.
  - Recomendar TCP quando houver perda de pacotes.
  - Detectar mensagens comuns nos logs do FFmpeg, como perda RTP.
  - Mostrar sugestao clara no painel quando uma camera estiver instavel.

- [ ] Melhorar erros e avisos no painel.
  - JSON de cameras invalido.
  - Pasta de gravacao sem permissao.
  - FFmpeg ou ffprobe ausente.
  - Camera sem gravacao recente.
  - Disco perto do limite.
  - Falha no live view.

- [ ] Remover dependencia de internet na interface.
  - Substituir CDN de icones por arquivos locais em `static/`.
  - Garantir que o painel funcione sem internet.
  - Evitar que TV Box ou Termux dependam de CDN externa.

- [ ] Melhorar armazenamento portatil.
  - Validar melhor Linux, TV Box e Android via Termux.
  - Detectar `$HOME/storage/shared` quando existir.
  - Detectar `/storage/emulated/0` e caminhos equivalentes.
  - Mostrar erro claro quando nao houver permissao.
  - Adicionar botao ou acao de testar escrita.

- [ ] Melhorar o script de inicializacao.
  - Adicionar comandos `start`, `stop`, `restart` e `status`.
  - Verificar FFmpeg e ffprobe antes de iniciar.
  - Evitar duplicar processos.
  - Parar filhos corretamente.
  - Mostrar IP local de acesso ao painel.

- [ ] Criar tela de saude do sistema.
  - FFmpeg instalado.
  - ffprobe instalado.
  - Captura ativa.
  - Limpeza ativa.
  - Ultima gravacao por camera.
  - Ultimo erro por camera.
  - Uso de disco.
  - Pasta ativa de gravacao.

- [ ] Melhorar gravacao em hardware fraco.
  - Manter `-c:v copy`.
  - Evitar conversoes desnecessarias.
  - Permitir desativar audio.
  - Permitir escolher stream principal ou substream.
  - Reduzir logs repetitivos.
  - Controlar melhor quantidade de processos FFmpeg.

## Prioridade baixa

- [ ] Organizar o backend em modulos menores.
  - Separar cameras, RTSP, videos, armazenamento e status.
  - Manter `servidor.py` mais focado nas rotas Flask.
  - Evitar refatoracao grande antes das melhorias de confiabilidade.

- [ ] Melhorar lista de gravacoes.
  - Adicionar paginacao.
  - Ordenacao por data/hora.
  - Mostrar duracao real.
  - Mostrar tamanho.
  - Manter botoes de player, download e apagar.

- [ ] Adicionar backup e restauracao.
  - Exportar cameras.
  - Importar cameras.
  - Exportar configuracoes locais sem expor credenciais indevidamente.

- [ ] Adicionar recuperacao de videos invalidos.
  - Tentar remux com FFmpeg.
  - Preservar arquivo original.
  - Mostrar resultado da tentativa no painel.

## Futuro

- [ ] Avaliar Docker depois da base ficar robusta.
  - Confirmar se Docker ajuda no PC Linux.
  - Confirmar limitacoes em TV Box ARM.
  - Confirmar se Android via Termux deve continuar sem Docker.

- [ ] Criar instalador simples.
  - Instalar dependencias quando possivel.
  - Verificar FFmpeg e ffprobe.
  - Criar pastas locais.
  - Criar `cameras.local.json` inicial quando nao existir.
  - Testar permissao de escrita.

## Ordem recomendada de execucao

1. Corrigir reproducao e duracao dos videos salvos.
2. Adicionar exclusao manual de videos.
3. Reforcar e testar limpeza automatica.
4. Permitir escolher segmento de 5, 10 ou 15 minutos.
5. Criar calendario de gravacoes.
6. Criar mosaico de cameras ao vivo.
7. Melhorar status real de cameras e saude do sistema.
8. Melhorar compatibilidade com Android/Termux e TV Box ARM.
