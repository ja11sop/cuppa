"""GitHub API access for maintenance scripts, with the credential kept out of the environment.

The token is sealed to this machine's TPM with `systemd-creds`, so the stored file is meaningless
anywhere else — on a backup, in a synced folder, or in a pasted diff. Sealing does not stop a
process running as you from asking this module for the token; what it stops is the file leaking.
Because of that, the credential is never exported into the environment, where every child process
of every shell would inherit it.

Seal or rotate a token:

    python -m scripts.github_api seal

Reads on a public repository use the anonymous API by default (GET / HEAD do not unseal):

    python -m scripts.github_api GET /repos/ja11sop/cuppa/issues/132
    python -m scripts.github_api GET /repos/ja11sop/cuppa/pulls/140 --auth   # sealed, if needed

    from scripts.github_api import GitHub
    GitHub.public().request( 'GET', '/repos/ja11sop/cuppa/pulls/139' )

Writes always use the sealed credential:

    from scripts.github_api import GitHub
    GitHub().request( 'POST', '/repos/ja11sop/cuppa/issues/132/labels', { 'labels': [ 'bug' ] } )
    python -m scripts.github_api PATCH /repos/ja11sop/cuppa/pulls/140 --data '{"title":"…"}'

Authenticated runs report how long the token has left, so rotation is prompted by use rather
than by a checklist nobody reads.
"""

import argparse
import datetime
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


API = 'https://api.github.com'
USER_AGENT = 'cuppa-maintenance'

CREDENTIAL_NAME = 'cuppa_github_token'
CREDENTIAL_FILE = os.path.join(
    os.path.expanduser( '~' ), '.config', 'cuppa', 'github-token.cred'
)

EXPIRY_HEADER = 'github-authentication-token-expiration'
EXPIRY_WARNING_DAYS = 3


class CredentialError( Exception ):
    pass


def seal( token, path=CREDENTIAL_FILE ):
    """Encrypt a token to this machine's TPM. Only this machine can read it back."""
    directory = os.path.dirname( path )
    if directory and not os.path.isdir( directory ):
        os.makedirs( directory, mode=0o700 )

    try:
        sealed = subprocess.run(
            [ 'systemd-creds', 'encrypt', '--with-key=tpm2',
              "--name={}".format( CREDENTIAL_NAME ), '-', '-' ],
            input = token.encode( 'utf-8' ),
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            check = True
        ).stdout
    except subprocess.CalledProcessError as error:
        raise CredentialError( "systemd-creds could not seal the token: {}".format(
            error.stderr.decode( 'utf-8', 'replace' ).strip() ) )
    except OSError as error:
        raise CredentialError( "systemd-creds is not available: {}".format( error ) )

    descriptor = os.open( path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 )
    with os.fdopen( descriptor, 'wb' ) as credential_file:
        credential_file.write( sealed )
    os.chmod( path, 0o600 )
    return path


def unseal( path=CREDENTIAL_FILE ):
    try:
        return subprocess.run(
            [ 'systemd-creds', 'decrypt', "--name={}".format( CREDENTIAL_NAME ), path, '-' ],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            check = True
        ).stdout.decode( 'utf-8' ).strip()
    except subprocess.CalledProcessError as error:
        raise CredentialError(
            "could not unseal [{}]: {}. A TPM clear or a move to another machine makes the "
            "sealed file unreadable; mint a new token and run: python -m scripts.github_api "
            "seal".format( path, error.stderr.decode( 'utf-8', 'replace' ).strip() )
        )
    except OSError as error:
        raise CredentialError( "systemd-creds is not available: {}".format( error ) )


def token():
    """The token, from the sealed credential, or from the environment with a warning."""
    if os.path.exists( CREDENTIAL_FILE ):
        return unseal()

    from_environment = os.environ.get( 'GITHUB_TOKEN' )
    if from_environment:
        warn( "using GITHUB_TOKEN from the environment, which every child process inherits. "
              "Seal it instead: python -m scripts.github_api seal" )
        return from_environment.strip()

    raise CredentialError(
        "no credential. Seal one with: python -m scripts.github_api seal"
    )


def warn( message ):
    sys.stderr.write( "warning: {}\n".format( message ) )


def report_expiry( header_value ):
    """Rotation is prompted by use: every run says how long the token has left."""
    if not header_value:
        return

    stamp = header_value.strip().replace( ' UTC', '' ).split( ' +' )[0]
    for form in ( '%Y-%m-%d %H:%M:%S', '%Y-%m-%d' ):
        try:
            expires = datetime.datetime.strptime( stamp, form )
            break
        except ValueError:
            expires = None
    if expires is None:
        return

    expires = expires.replace( tzinfo=datetime.timezone.utc )
    days = ( expires - datetime.datetime.now( datetime.timezone.utc ) ).days
    if days <= EXPIRY_WARNING_DAYS:
        warn( "the GitHub token expires in {} day(s), on {}. Mint a replacement and run: "
              "python -m scripts.github_api seal".format( days, expires.date() ) )
    else:
        sys.stderr.write( "GitHub token expires in {} days, on {}\n".format(
            days, expires.date() ) )


class GitHub( object ):
    """Minimal API client.

    Authenticated instances hold the token in memory only, and never in the environment.
    Anonymous instances omit the credential entirely — enough for reads on a public repository,
    which is what status helpers should use so watching CI does not unseal the token every poll.
    """

    def __init__( self, credential=None, anonymous=False ):
        if anonymous:
            self._token = None
        else:
            self._token = credential if credential is not None else token()
        self._expiry_reported = False

    @classmethod
    def public( cls ):
        """Unauthenticated client for public repository reads."""
        return cls( anonymous=True )

    def request( self, method, path, payload=None ):
        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': USER_AGENT,
        }
        if self._token is not None:
            headers['Authorization'] = 'Bearer ' + self._token

        request = urllib.request.Request(
            path if path.startswith( 'http' ) else API + path,
            data = json.dumps( payload ).encode( 'utf-8' ) if payload is not None else None,
            method = method,
            headers = headers,
        )
        try:
            with urllib.request.urlopen( request ) as response:
                self._report_expiry_once( response.headers )
                body = response.read()
                return response.status, ( json.loads( body ) if body else {} )
        except urllib.error.HTTPError as error:
            self._report_expiry_once( error.headers )
            body = error.read()
            return error.code, ( json.loads( body ) if body else {} )

    def download( self, path ):
        """Authenticated GET returning raw ``bytes`` (for zip log archives and similar).

        GitHub redirects log downloads to object storage. Forwarding the Bearer token to that
        host fails authentication, so Authorization is dropped on cross-host redirects.
        """
        if self._token is None:
            raise CredentialError(
                "download requires the sealed credential "
                "(python -m scripts.github_api seal)"
            )

        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': USER_AGENT,
            'Authorization': 'Bearer ' + self._token,
        }
        request = urllib.request.Request(
            path if path.startswith( 'http' ) else API + path,
            method = 'GET',
            headers = headers,
        )

        class _StripAuthRedirect( urllib.request.HTTPRedirectHandler ):
            def redirect_request( self, req, fp, code, msg, headers, newurl ):
                new_request = urllib.request.HTTPRedirectHandler.redirect_request(
                    self, req, fp, code, msg, headers, newurl
                )
                if new_request is None:
                    return None
                if 'api.github.com' not in new_request.full_url:
                    for header_name in list( new_request.headers ):
                        if header_name.lower() == 'authorization':
                            del new_request.headers[header_name]
                    unredirected = getattr( new_request, 'unredirected_hdrs', None )
                    if unredirected:
                        for header_name in list( unredirected ):
                            if header_name.lower() == 'authorization':
                                del unredirected[header_name]
                return new_request

        opener = urllib.request.build_opener( _StripAuthRedirect )
        try:
            with opener.open( request ) as response:
                self._report_expiry_once( response.headers )
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            self._report_expiry_once( error.headers )
            body = error.read()
            try:
                payload = json.loads( body ) if body else {}
            except ( TypeError, ValueError ):
                payload = { 'message': body.decode( 'utf-8', 'replace' ) if body else '' }
            return error.code, payload

    def _report_expiry_once( self, headers ):
        if self._token is None or self._expiry_reported:
            return
        self._expiry_reported = True
        report_expiry( headers.get( EXPIRY_HEADER ) )


def seal_command():
    if sys.stdin.isatty():
        value = getpass.getpass( 'Paste the GitHub token (not echoed): ' ).strip()
    else:
        value = sys.stdin.read().strip()

    if not value:
        print( "No token given" )
        return 1

    path = seal( value )
    if unseal( path ) != value:
        print( "The sealed credential did not read back correctly; not trusting it" )
        return 1

    print( "Sealed to {} (mode 600, readable only on this machine)".format( path ) )
    status, _ = GitHub().request( 'GET', '/user' )
    print( "GitHub responded {} to an authenticated request".format( status ) )
    return 0 if status == 200 else 1


# Safe methods default to the anonymous client so a casual GET does not unseal the token.
PUBLIC_METHODS = frozenset( { 'GET', 'HEAD' } )


def main( argv=None ):
    parser = argparse.ArgumentParser( description=__doc__ )
    parser.add_argument( 'method', help="an HTTP method, or 'seal' to store a token" )
    parser.add_argument( 'path', nargs='?', help="an API path, for example /repos/owner/name" )
    parser.add_argument( '--data', help="a JSON request body" )
    parser.add_argument(
        '--auth', action='store_true',
        help="unseal the credential (default for writes; optional for GET/HEAD)",
    )
    arguments = parser.parse_args( argv )

    try:
        if arguments.method == 'seal':
            return seal_command()

        if not arguments.path:
            print( "Give an API path" )
            return 1

        method = arguments.method.upper()
        payload = json.loads( arguments.data ) if arguments.data else None
        use_public = method in PUBLIC_METHODS and not arguments.auth
        client = GitHub.public() if use_public else GitHub()
        status, body = client.request( method, arguments.path, payload )
    except CredentialError as error:
        print( "Credential error: {}".format( error ) )
        return 1

    print( json.dumps( body, indent=2 ) )
    return 0 if status < 400 else 1


if __name__ == '__main__':
    sys.exit( main() )
