# Bestiário de Arton — compêndio para Foundry VTT (Tormenta20)

181 ameaças do *Bestiário de Arton* como atores NPC do sistema **tormenta20**, em pastas por ND.

- Foundry 13 + sistema Tormenta20 1.5.x
- Foundry 14 + sistema Tormenta20 1.6.x

## Instalação
1. Descompacte a pasta `bestiario-de-arton-t20` em `Data/modules/` (dados do usuário do Foundry).
2. No mundo, ative o módulo em *Configurações > Gerenciar Módulos*.
3. O compêndio aparece na aba Compêndios, na pasta "Bestiário de Arton". Arraste a criatura para a cena ou importe.

## O que cada ficha tem
- Atributos, PV, PM, Defesa, resistências e perícias calculados para bater com o livro.
- Ataques como armas naturais que rolam ataque e dano.
- Habilidades como poderes, com tipo de ação e custo em PM.
- Magias copiadas do compêndio de magias do sistema, com o uso da criatura no topo.
- Texto completo da ficha na biografia, com a página do livro.

Conteúdo © Jambô Editora. Este módulo é só para uso pessoal de quem tem o livro: não distribua.

## Instalação pelo manifesto
O repositório é privado, então o Foundry não consegue baixar pela URL do manifesto sem autenticação.
Baixe o `bestiario-de-arton-t20.zip` da [última release](https://github.com/fernandowrpg/t20-bestiario/releases/latest) e descompacte em `Data/modules/`.

## Desenvolvimento
- `src/packs/bestiario-de-arton/`: fontes JSON das criaturas e pastas (formato do `@foundryvtt/foundryvtt-cli`).
- `npm ci && npm run build -- 1.0.1`: compila o compêndio LevelDB em `dist/`.
- `tools/`: extração a partir do PDF (não versionado).
  1. `python3 tools/t20ameacas.py tools/config.json`: gera `saida/threats.json` (com o PDF em `Bestiario-de-Arton.pdf`).
  2. `python3 tools/build_foundry.py saida/threats.json <sistema-tormenta20>/packs/_source/magias src/packs/bestiario-de-arton`: gera os atores, ligando as magias ao compêndio do sistema 1.5.x.

## Release automática
Crie e envie uma tag `v*` (por exemplo, `git tag v1.0.1 && git push origin v1.0.1`) ou rode o workflow **Release** manualmente pela aba Actions, informando a versão.
O workflow compila o compêndio e publica a release com `bestiario-de-arton-t20.zip` e `module.json`.
