#!/usr/bin/env python3
#------------------------------------------------------------------------------
#
# Name: cert_request.py
# Usage: request_cert.py -f/--fqdn <subject-fqdn> -c/--csr <csr-filename> [-v/--validity <days>]
#
# Version: 2019.01
# Date: 2019-10-26
#
# Author: @timcappalli
#
# (c) Copyright 2019 Tim Cappalli.
#
# Licensed under the MIT license:
#
#    http://www.opensource.org/licenses/mit-license.php
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#------------------------------------------------------------------------------

__version__ = "2019.01"

import json
import requests
import dns.resolver
import time
import os
from configparser import ConfigParser
import argparse

# configuration file parameters
params = os.path.join(os.path.dirname(__file__), "config")
config = ConfigParser()
config.read(params)

# CertCenter config
CC_PRODUCT_CODE = config.get('CertCenter', 'product_code')
CC_CERT_VALID_CONFIG = config.get('CertCenter', 'cert_validity_period')

CC_CLIENT_ID = config.get('CertCenter', 'client_id')
CC_CLIENT_SECRET = config.get('CertCenter', 'client_secret')
CC_TOKEN_ENDPOINT = 'https://api.certcenter.com/oauth2/token'
CC_SCOPE = 'order'


def token_handling():

    if os.path.isfile("token.json"):

        with open('token.json') as f:
            token_file = json.load(f)

        current_time_plus_thirty = time.time() + 30

        # check cached token validity
        if token_file['expires_at'] > current_time_plus_thirty:
            access_token = token_file['access_token']
            print("\tUsing cached access token.")

            if DEBUG:
                print(f"\t[DEBUG] Access Token: {access_token}")

            return access_token

    else:
        # check config
        if not CC_CLIENT_ID or not CC_CLIENT_SECRET:
            print("ERROR: client_id or client_secret not defined in config file.")
            exit(1)
        else:
            # get new token
            print("\tNo cached token. Acquiring new token.")

            url = CC_TOKEN_ENDPOINT
            headers = {'Content-Type': 'application/json'}
            payload = {'grant_type': 'client_credentials', 'client_id': CC_CLIENT_ID, 'client_secret': CC_CLIENT_SECRET, 'scope': CC_SCOPE}

            try:
                r = requests.post(url, headers=headers, json=payload)
                r.raise_for_status()

                json_response = json.loads(r.text)

                if DEBUG:
                    print(json_response)

                # token caching
                token_expiration = int(json_response['expires_in'] + time.time())
                token_cache = {'access_token': json_response['access_token'], 'expires_at': token_expiration, 'host': CC_TOKEN_ENDPOINT}
                with open('token.json', 'w') as tokenfile:
                    json.dump(token_cache, tokenfile)

                return json_response['access_token']

                # TODO: add refresh token

            except Exception as e:
                if r.status_code == 400:
                    print("ERROR: Check config.py (client_id, client_secret)")
                    print("\tRaw Error Text: {}".format(e))
                    exit(1)
                else:
                    print(e)
                    exit(1)


def cc_validate_name(cc_access_token, cert_fqdn):
    """Validate FQDN for certificate eligibility against CertCenter API

    Requires CertCenter access token and requested FQDN

    """
    try:
        url = "https://api.certcenter.com/rest/v1/ValidateName"

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(cc_access_token)
        }

        payload = {
            "CommonName": cert_fqdn
        }

        r = requests.post(url=url, headers=headers, json=payload)

        json = r.json()

        if not json['success']:
            print("\tCertCenter authorization failed. Check access token.")
            print("\n\t\t{}".format(r.text))
            exit(1)
        elif json['IsQualified']:
            print("\tAuthorization successful! Domain qualified.")
            return json
        else:
            print("\n\tUnknown error.")
            print("\n\t\t{}".format(r.text))
            exit(1)

    except Exception as e:
        print("\n\t{}".format(e))
        exit(1)


def cc_get_dns_data(cc_access_token, csr):
    """Get DNS validation data via CertCenter REST API

    Requires CertCenter access token and CSR for FQDN

    """

    try:
        url = "https://api.certcenter.com/rest/v1/DNSData"

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(cc_access_token)
        }

        payload = {
            "CSR": csr,
            "ProductCode": CC_PRODUCT_CODE
        }

        r = requests.post(url=url, headers=headers, json=payload)
        json = r.json()

        txt_value = json['DNSAuthDetails']['DNSValue']
        txt_example = json['DNSAuthDetails']['Example']

        #print("\n\t{}".format(txt_example))

        if DEBUG:
            print(f"\tDEBUG: {json}\n")

        return txt_value

    except Exception as e:
        print("\n\t{}".format(e))
        print(f"\t{r.text}")
        exit(1)


def verify_dns_record(cert_fqdn, txt_value):
    """Verify DNS record matches and record has propagated to Google DNS

    Requires FQDN and expected TXT value from CertCenter

    """

    found = False

    print("\n\tWaiting 30 seconds for global DNS propagation...")
    time.sleep(30)

    while not found:
        try:
            dns_resolver = dns.resolver.Resolver()
            dns_resolver.nameservers = ['8.8.8.8']
            dns_answers = dns_resolver.query(cert_fqdn, "TXT")

            found = True

            print("\n\tRecord found! Verifying...")

            time.sleep(3)

            for rdata in dns_answers:

                value = str(rdata)

                if value == "\"{}\"".format(txt_value):
                    accurate = True
                else:
                    accurate = False

        except:
            found = False
            print("\n\tDNS record still not found. Waiting another 30 seconds before next lookup attempt...")
            time.sleep(30)

    if accurate:
        print("\n\tTXT record matches!")
        return True
    else:
        print("\n\tTXT record does NOT match")
        exit(1)


def cc_request_cert(cc_access_token, csr, cc_cert_validity_period):
    """Request certificate from CertCenter via REST API

    Requires CertCenter access token, CSR (PKCS #10 format), CertCenter product code and cert validity period

    """
    try:
        url = "https://api.certcenter.com/rest/v1/Order"

        headers = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(cc_access_token)}

        payload = {
            "OrderParameters": {
                "ProductCode": CC_PRODUCT_CODE,
                "CSR": csr,
                "ValidityPeriod": int(cc_cert_validity_period),
                "DVAuthMethod": "DNS"
            }
        }

        r = requests.post(url=url, headers=headers, json=payload)

        json = r.json()

        if json['success']:
            results = {
                "pkcs7": json['Fulfillment']['Certificate_PKCS7'],
                "intermediate": json['Fulfillment']['Intermediate'],
                "signed_cert": json['Fulfillment']['Certificate'],
                "expiration": json['Fulfillment']['EndDate']
            }

            print("\n\tCertificate request successful!\n\tExpiration: {}".format(json['Fulfillment']['EndDate']))

            return results

        else:
            print("\n\tCERTIFICATE REQUEST FAILED")
            print("\n\t\t{}".format(r.text))
            exit(1)

    except Exception as e:
        print("\n\t{}".format(e))
        exit(1)


def dump_cert(cert_fqdn, signed_cert, intermediate):
    """Dumps out cert and chained cert to files (PEM)

    Requires cert FQDN, signed cert and intermediate returned from CertCenter

    """
    try:
        file = open("{}_cert.pem".format(cert_fqdn), "w")
        file.write(signed_cert)
        file.close()

        print("\n\tCertificate exported: {}_cert.pem".format(cert_fqdn))

    except Exception as e:
        print("\n\t{}".format(e))
        exit(1)

    try:
        file = open("{}_cert-chained.pem".format(cert_fqdn), "w")
        file.write(signed_cert)
        file.write("\n")
        file.write(intermediate)
        file.close()

        print("\n\tChained certificate exported: {}_cert-chained.pem".format(cert_fqdn))

    except Exception as e:
        print("\n\t{}".format(e))
        exit(1)


if __name__ == '__main__':

    # process arguments
    parser = argparse.ArgumentParser(
        description='Cert request for CertCenter'
    )

    required_args = parser.add_argument_group('Required arguments')
    required_args.add_argument("-f", "--fqdn", help="FQDN", required=True)
    required_args.add_argument("-c", "--csr", help="CSR filename", required=True)
    parser.add_argument("-d", "--days", help="Cert Validity in days, 1-365 (optional)", required=False)
    parser.add_argument("-v", "--verbose", help="Verbose logging", required=False, action='store_true')

    DEBUG = False

    args = parser.parse_args()

    cert_fqdn = args.fqdn
    csr_filename = args.csr

    if args.verbose:
        DEBUG = True

    if args.days:
        validity_period = args.days
    else:
        validity_period = CC_CERT_VALID_CONFIG

    with open(csr_filename, 'r') as f:
        csr = f.read()

    # get CertCenter access token
    print("\n[1] Getting access token...")
    token = token_handling()

    # validate domain against CertSimple
    print("\n[2] Validating domain with CertCenter...")
    cc_validate_name(token, cert_fqdn)

    # get DNS validation value from CertSimple
    print("\n[3] Getting domain validation information from CertCenter...")
    txt_value = cc_get_dns_data(token, csr)

    print(f"\tDNS TXT Value is: {txt_value}")
    input("\nPress Enter after DNS record creation...\n")

    # verify DNS propagation
    print("\n[5] Attempting to verify DNS record...")
    txt_match = verify_dns_record(cert_fqdn, txt_value)

    # request certificate
    print("\n[6] Requesting certificate from CertCenter...")
    cert_output = cc_request_cert(token, csr, validity_period)

    # dump signed certificate to file
    print("\n[7] Exporting signed certificate with chain...")
    dump_cert(cert_fqdn, cert_output['signed_cert'], cert_output['intermediate'])

    print("\n\nPROCESS COMPLETE!\n\n")
    exit(0)
