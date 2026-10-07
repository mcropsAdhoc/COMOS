FROM openpolicyagent/opa:latest-static
COPY commos.rego /policies/commos.rego
EXPOSE 8080
CMD ["run","--server","--addr=0.0.0.0:8080","/policies/commos.rego"]
