# Projeto Cloud

Script para criar toda a infraestutura de uma aplicação na AWS.

## Bibliotecas necessárias

1) Boto3

```
pip3 install boto3
```

## Execução

1) Atualize o arquivo [set_env](https://github.com/decoejz/projeto-cloud/blob/master/set_env) com as suas credenciais

2) No terminal execute

```
source set_env
```

3) Ainda no terminal, execute

```
python3 awsAPI.py
```

## Repositórios utilizados:

1) [Aplicação (Webserver) + Client da aplicação](https://github.com/decoejz/APS-cloud-comp.git)

2) [Repositório com arquivo de redirect](https://github.com/decoejz/redirect_ws_cloud.git)
