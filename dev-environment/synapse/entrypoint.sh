#!/bin/sh

# This is a hack to predefine users. The command will not work for a
# while until synapse is up and running. Please suggest better ways
# to achieve this :-)
infinite_register() {
    while true
    do
        if register_new_matrix_user -c /homeserver.yaml -u "$1" -p "$1" --no-admin http://localhost:8008 > /dev/null 2>&1;
        then
            break
        fi
        sleep 2
    done
}

(infinite_register dev)&

eval /start.py
