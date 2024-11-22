#!/usr/bin/env python
# Copyright (c) 2019 ACSONE SA/NV
# Distributed under the MIT License (http://opensource.org/licenses/MIT)

from __future__ import print_function

import os
import sys

import googleapiclient.discovery
import google.auth
import google.auth.exceptions

_, PROJECT_ID = google.auth.default()

import requests

CHUNK_SIZE = 2 ** 16


def get_service_url():
    try:
        service = googleapiclient.discovery.build('run', 'v1')
    except google.auth.exceptions.DefaultCredentialsError as Exc:
        raise Error(Exc)
    else:
        k_service = os.environ['K_SERVICE']
        parent = f'namespaces/{PROJECT_ID}'

        request = service.namespaces().services().list(parent=parent)
        response = request.execute()

        serv_url = ""
        for item in response['items']:
            if item['metadata']['name'] == k_service:
                serv_url = item['status']['url']
                break

    return serv_url


class Error(Exception):
    pass


class UsageError(Error):
    pass


class ServerError(Error):
    pass


def wkhtmltopdf(args):
    url = os.getenv("KWKHTMLTOPDF_SERVER_URL")
    parts = []

    def add_option(option):
        # TODO option encoding?
        parts.append(("option", (None, option)))

    def add_file(filename):
        with open(filename, "rb") as f:
            parts.append(("file", (filename, f.read())))

    if "-" in args:
        raise UsageError("stdin/stdout input is not implemented")

    output = "-"
    if len(args) >= 2 and not args[-1].startswith("-") and not args[-2].startswith("-"):
        output = args[-1]
        args = args[:-1]

    for arg in args:
        if arg.startswith("-"):
            add_option(arg)
        elif arg.startswith("http://") or arg.startswith("https://"):
            add_option(arg)
        elif arg.startswith("file://"):
            add_file(arg[7:])
        elif os.path.isfile(arg):
            # TODO better way to detect args that are actually options
            # TODO in case an option has the same name as an existing file
            # TODO only way I see so far is enumerating them in a static
            # TODO datastructure (that can be initialized with a quick parse
            # TODO of wkhtmltopdf --extended-help)
            add_file(arg)
        else:
            add_option(arg)

    if not parts:
        add_option("-h")

    try:
        audience = get_service_url()
        endpoint = url
        req = urllib.request.Request(endpoint)
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
        headers = {
            "Authorization": f"Bearer {id_token}",
        }
        r = requests.post(url, files=parts, headers=headers)
        r.raise_for_status()

        if output == "-":
            if sys.version_info[0] < 3:
                out = sys.stdout
            else:
                out = sys.stdout.buffer
        else:
            out = open(output, "wb")
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            out.write(chunk)
    except requests.exceptions.ChunkedEncodingError:
        # TODO look if client and server could use trailer headers
        # TODO to report errors
        raise ServerError("kwkhtmltopdf server error, consult server log")


if __name__ == "__main__":
    try:
        wkhtmltopdf(sys.argv[1:])
    except Error as e:
        print(e, file=sys.stderr)
        sys.exit(-1)
