#!/usr/bin/env bash
export WEB_TOKEN="meu_token_seguro_aqui"   # opcional: você também pode usar o painel do Render
gunicorn app:app --bind 0.0.0.0:$PORT
