FROM alpine:3.14

ARG version=v1.32.0

RUN wget -O /aws-opentelemetry-agent.jar  \
            https://github.com/aws-observability/aws-otel-java-instrumentation/releases/download/$version/aws-opentelemetry-agent.jar

ADD entrypoint.sh /entrypoint.sh

RUN chmod u+x /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
