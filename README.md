# Sistema de Gestão de Doações Comunitárias

MVP acadêmico para cadastro de doações, consulta de estoque, registro de distribuições e histórico.

## Tecnologias
Python 3.12, Flask, SQLite, HTML/CSS, pytest e GitHub Actions.

## Instalação
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Defina uma chave secreta forte na variável `SECRET_KEY` antes de compartilhar ou publicar a aplicação. Crie um usuário:
```bash
flask --app app create-user
```
O comando solicitará usuário e senha (mínimo de 12 caracteres). A senha será armazenada como hash.

Execute:
```bash
flask --app app run
```
Acesse http://127.0.0.1:5000.

Testes:
```bash
pytest -q
```

## Funcionalidades
- Cadastro de doações e atualização do saldo.
- Consulta e pesquisa de estoque.
- Distribuição com bloqueio de saldo insuficiente.
- Histórico de entradas e saídas.
- Login com hash de senha e rotas protegidas.
- Teste automatizado básico e pipeline CI.

## Limites
Projeto acadêmico inicial. Antes de uso real, realize revisão de segurança, backup, testes adicionais e validação com representantes comunitários. SQLite atende ao protótipo local; uso concorrente pode exigir banco de dados servidor.
