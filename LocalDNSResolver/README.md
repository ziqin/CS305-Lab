# Local DNS Resolver

## Environment Requirement

Python 3.7+ is required

## Usage

```bash
python dns_resolver.py
```

You may need root privilege to run the resolver using the 53 port, or you can change the port number by modifing the source code.

## Notice

Since time is limited, the cache strategy implemented is simplied and does not follows the standard protocol. Please do not use it in production environment.