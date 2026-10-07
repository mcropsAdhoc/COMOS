FROM openpolicyagent/opa:latest-static
COPY commos.rego /policies/commos.rego
EXPOSE 8181
CMD ["run","--server","--addr=0.0.0.0:8181","/policies/commos.rego"]
