# Hight Level Description
[!diagram](docs/base_infrastructure.drawio.png)

This diagram is the hight level view of the infrastructure created by 3 different templates.

- [Once 4 account](once4account) creates _Alarm Topic_ 
- [pn-ipc.yaml](pn-ipc.yaml) create the SQS queues used to comunicate between microservices
- [pn-infra.yaml](pn-infra.yaml) all the rest except _ECS microservices_

The _ECS microservices_ and their API exposition are configured in each microservice project using the 
[ecs-service.yaml](fragments/ecs-service.yaml) and 
[api-gw-expose-service.yaml](fragments/api-gw-expose-service.yaml) CFN templates fragments.
