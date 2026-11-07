FROM golang:1.23-alpine AS go
WORKDIR /src
COPY scanners/find-dead-go-statements.go .
RUN go mod init deadgo >/dev/null 2>&1 && CGO_ENABLED=0 go build -o /dead-go-statements find-dead-go-statements.go

FROM python:3.13-alpine
LABEL org.opencontainers.image.source="https://github.com/dylanpulver/dead-tests" \
      org.opencontainers.image.description="Find tests that look like coverage but can never fail or never run" \
      org.opencontainers.image.licenses="MIT"
WORKDIR /opt/deadtests
COPY deadtests ./
COPY scanners ./scanners
COPY --from=go /dead-go-statements ./scanners/dead-go-statements
RUN ln -s /opt/deadtests/deadtests /usr/local/bin/deadtests
WORKDIR /src
ENTRYPOINT ["deadtests"]
CMD ["scan", "."]
