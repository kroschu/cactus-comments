# Hacking

Thank you for being interested in Cactus Comments! Contributions are very
welcome! This document is here to help you get started hacking on the
backend/appservice.


## Getting Started

To start hacking you need [git](https://git-scm.com/downloads),
[docker](https://docs.docker.com/engine/install/),
[docker-compose](https://docs.docker.com/compose/install/) and your favorite
`$EDITOR`.

First, clone the repo:

    $ git clone https://gitlab.com/cactus-comments/cactus-appservice
    $ cd cactus-appservice

Second, start the environment:

    $ docker-compose up -d


## The environment

The development environment contains only two services: a local synapse
accessible at localhost:8008 and a matrix client (element) at localhost:8085.

3 users have been pre-registered for you: "dev1", "dev2" and "dev3". Their
passwords equal their usernames. "@dev1:localhost:8008" is the full name of
dev1. Try to access Element and start a chat with the appservice
"@cactusbot:localhost:8008".


## Useful commands

I recommend you follow the logs while developing:

    $ docker-compose logs -f app

You can rebuild and restart the app with:

    $ docker-compose up -d --build

The app should restart when you make changes. You can force a restart with:

    $ docker-compose restart app

To run the tests:

    $ docker-compose exec app pytest
