# CertCenter Cert Request

This is a basic script that helps to automate most parts of a certificate request from the Encryption Everywhere service (DigiCert) via CertCenter. 

This script requires manual DNS record creation. If you're using AWS Route 53, see [certcenter-r53-cert-request](https://github.com/timcappalli/certcenter-r53-cert-request) for a completely automated solution.

What it does:
1. Checks the domain against CertCenter for eligibility 
2. Requests domain validation challenge (TXT record)
3. Presents TXT record value and waits for user confirmation
4. Tests public DNS for TXT record presence
5. Submits the CSR for signing
6. Dumps out the signed cert with chain



## Configuration
Create a file named 'config' (no extension) with the contents below and fill in the appropriate values.

```
[CertCenter]
client_id = 
client_secret = 
product_code = AlwaysOnSSL.AlwaysOnSSL
cert_validity_period = 365
```

## Usage

`request_cert.py -f/--fqdn <subject-fqdn> -c/--csr <csr-filename> [-v/--validity <days>]`

Required Arguments:
* `--fqdn / -f`: The FQDN from the CN
* `--c / -c`: the filename of the CSR

Optional Arguments:
* `--days / -d`: override validity from config file (1-365)
* `--verbose / -v`: verbose logging 

### Examples

`request_cert.py --fqdn=host.domain.com --csr=host.csr `

`request_cert.py -f host.domain.com -c host.csr`

## Change Log
#### 2019.03 (2019-12-31)
* Fixed token caching

#### 2019.02 (2019-12-30)
* Fixed an issue where the root certificate and extra blank lines were included in the chained output due to an undocumented change by DigiCert

#### 2019.01 (2019-10-26)
* Initial release

## License and Other Information
This repo is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

Author: @timcappalli