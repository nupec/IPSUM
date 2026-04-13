# Guia de Contribuição - IPSUM Backend

Este documento estabelece as diretrizes e padrões técnicos para contribuições no repositório de backend do projeto IPSUM. O cumprimento destas normas é essencial para garantir a integridade da arquitetura, a segurança do código e a facilidade de manutenção a longo prazo.

## 1. Código de Conduta

Ao contribuir para este projeto, você assume o compromisso de manter um ambiente colaborativo e profissional. O detalhamento das normas de convivência pode ser consultado no arquivo `CODE_OF_CONDUCT.md`.

## 2. Processo de Contribuição

As contribuições são gerenciadas através de Issues e Pull Requests. Nenhuma alteração deve ser enviada diretamente para as branches principais.

### 2.1 Reporte de Falhas (Bugs)
Para reportar um erro técnico:
1. Verifique se o problema já foi listado nas Issues abertas.
2. Utilize o template de reporte de bug, fornecendo:
   - Descrição técnica do erro;
   - Logs do container Docker;
   - Passos exatos para reprodução;
   - Comportamento esperado versus comportamento observado.

### 2.2 Sugestões de Funcionalidades
Sugestões de novas implementações ou melhorias arquiteturais devem ser discutidas previamente via Issue para validação da viabilidade técnica e alinhamento com os objetivos do projeto ResiliSUS/FIOCRUZ.

## 3. Fluxo de Desenvolvimento (Git Flow)

Este repositório utiliza uma adaptação do GitHub Flow. A branch de integração principal é a `deploy-backend`.

### 3.1 Branches
- `deploy-backend`: Branch estável para homologação.
- `feature/nome-da-funcionalidade`: Para novas implementações.
- `hotfix/nome-da-correcao`: Para correções críticas.

### 3.2 Passo a Passo
1. Realize o fork do repositório.
2. Crie uma branch a partir da `deploy-backend`.
3. Implemente as alterações seguindo os padrões de codificação.
4. Realize testes locais via Docker.
5. Envie um Pull Request apontando para a branch `deploy-backend`.

## 4. Ambiente de Desenvolvimento

O ambiente é inteiramente containerizado para garantir a paridade entre os sistemas de desenvolvimento e produção.

### 4.1 Pré-requisitos
- Docker Engine instalado.
- Docker Compose instalado.

### 4.2 Configuração
```bash
git clone https://github.com/nupec/IPSUM-backend.git
cd IPSUM-backend
docker-compose up --build
```

## 5. Padrões Técnicos

### 5.1 Codificação em Python
- Siga rigorosamente a PEP 8.
- Utilize tipagem estática (Type Hints) em todas as funções e métodos.
- Documente classes e funções complexas utilizando o padrão Google Python Style Guide.

### 5.2 Segurança e Cibersegurança
Dado o foco em segurança da informação do projeto:
- Não submeta arquivos de configuração (.env) ou segredos no histórico do Git.
- Valide rigorosamente todos os inputs de usuários via Pydantic.
- Certifique-se de que novas rotas passem pelas camadas de autenticação e autorização configuradas.

### 5.3 Mensagens de Commit
Utilize commits semânticos (Conventional Commits) para manter o histórico legível:
- `feat:` para novas funcionalidades.
- `fix:` para correção de bugs.
- `refactor:` para alterações em código que não corrigem bugs nem adicionam funcionalidades.
- `docs:` para alterações em documentação.

## 6. Revisão de Código (Code Review)

Todos os Pull Requests passarão por revisão técnica antes da integração. Os revisores observarão:
- Manutenibilidade do código.
- Eficiência dos algoritmos de geoprocessamento.
- Tratamento adequado de exceções e falhas nos motores de rota (Valhalla).
- Cobertura de testes, quando aplicável.

---

### Observações sobre o seu envio (Git)
Para o seu commit atual, após salvar o arquivo acima, você pode utilizar os seguintes comandos no terminal para garantir que as alterações no backend sejam enviadas corretamente:

```bash
git add CONTRIBUTING.md
git commit -m "docs: adicionar guia de contribuicao para o backend"
git push origin feature/nome-da-sua-branch
```

Se precisar de ajuda para configurar o repositório remoto (visto que agora os repositórios estão separados), posso lhe passar os comandos de `git remote set-url`.