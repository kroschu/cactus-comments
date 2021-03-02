![](./appservice-banner.png)

[Cactus Comments](https://cactus.chat) is a federated comment system that you
can embed anywhere. It respects your privacy, and puts you in control.

This is the [application
service](https://matrix.org/docs/guides/application-services) backend for
https://cactus.chat. It is a [flask](https://flask.palletsprojects.com/)
application written in [Python](https://python.org). It interacts with the
matrix server with pure HTTP calls and not through an SDK. If you want to
deploy this, we recommend the [docker
image](https://hub.docker.com/r/cactuscomments/cactus-appservice). If you want
to hack on this, see [HACKING.md](./HACKING.md). You can chat with us in [the
official Cactus Comments Matrix room](https://matrix.to/#/#cactus:bordum.dk).


## Say hello to cactusbot

This application is deployed and freely availble. To interact with it, start a
chat with
[`@cactusbot:cactus.chat`](https://matrix.to/#/@cactusbot:cactus.chat). You can
get started by typing `"help"` or visiting
https://cactus.chat/docs/getting-started.


## What is this?

This part of the stack is mainly interacted with by site administrators. The
purpose is to assign everyone a site, provide an interactive user interface and
to help ease moderation. For now, this services creates rooms with proper
permissions / initial configuration, bans users across your entire site
and promotes moderators across your entire site.


## Configuration

Cactus Comments is free and open source software and you can run it yourself.
Here we describe how to set it up in docker, connecting to Synapse.


### Synapse

First off, we need to register this appservice with Synapse.

Let's call the file `cactus-appservice.yaml`. Synapse needs to be able to read
this file. Use this file as an sample and be sure to change the tokens:

```yaml
# A unique, user-defined ID of the application service which will never change.
id: "Cactus Comments"

# Where the service is hosted:
url: "http://cactus:5000"

# Unique tokens used to authenticate requests between our service and the
# homeserver (and the other way). Use the sha256 hashes of something random.
# CHANGE THESE VALUES.
as_token: "a2d7789eedb3c5076af0864f4af7bef77b1f250ac4e454c373c806876e939cca"
hs_token: "b3b05236568ab46f0d98a978936c514eac93d8f90e6d5cd3895b3db5bb8d788b"

# User associated with our service. In this case "@cactusbot:yourserver.org"
sender_localpart: "cactusbot"

namespaces:
  aliases:
    - exclusive: true
      regex: "#comments_.*"
```

Then you should add the file path to your synapse `homeserver.yaml`:

``` yaml
app_service_config_files:
  - "/path/to/cactus-appservice.yaml"
```

Additionally, you can set `allow_guest_access: true`, to allow visitors to read
comments without logging in.


### cactus-appservice

The application service is entirely configured with environment variables. If
you have changed the namespace room alias in the appservice registration above,
you need to set `CACTUS_NAMESPACE_REGEX` and `CACTUS_NAMESPACE_PREFIX`.
Otherwise, you just need 4 environment variables. Assume, that the following is
saved to a file, `cactus.env`:

```
CACTUS_HS_TOKEN=b3b05236568ab46f0d98a978936c514eac93d8f90e6d5cd3895b3db5bb8d788b
CACTUS_AS_TOKEN=a2d7789eedb3c5076af0864f4af7bef77b1f250ac4e454c373c806876e939cca
CACTUS_HOMESERVER_URL=http://synapse:8008
CACTUS_USER_ID=@cactusbot:yourserver.org
```

In `docker`, you need to run something like:

```sh
$ docker run --env-file cactus.env --name cactus cactuscomments/cactus-appservice:latest
```


In `docker-compose`, this service might look like:

```yaml
services:
  cactus:
    image: cactuscomments/cactus-appservice:latest
    env_file: "cactus.env"
```
