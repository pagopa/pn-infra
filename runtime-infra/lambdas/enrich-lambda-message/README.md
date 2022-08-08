# Istruzione per costruire il package zip

```shell
pip install --target ./package requests
cd package
zip -r ../enrich-lambda-message.zip .
cd ..
zip -g enrich-lambda-message.zip enrich-lambda-message.py
```

