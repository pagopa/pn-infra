FROM alpine:3.14@sha256:0f2d5c38dd7a4f4f733e688e3a6733cb5ab1ac6e3cb4603a5dd564e5bfb80eed

ARG version=v1.32.0

RUN wget -O /aws-opentelemetry-agent.jar  \
            https://github.com/aws-observability/aws-otel-java-instrumentation/releases/download/$version/aws-opentelemetry-agent.jar

ADD entrypoint.sh /entrypoint.sh

RUN chmod u+x /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
