#!/usr/bin/env just --justfile

default:
    @just --list

n_root := "projects/nautobot/dev_data"

nauto_run *ARGS:
    #!/usr/bin/env bash
    export NAUTOBOT_ROOT="{{n_root}}"
    export ENV_PATH="{{n_root}}/.env"
    nautobot-server {{ARGS}}

nauto_start *ARGS:
    just nauto_run start --ini {{n_root}}/uwsgi.ini