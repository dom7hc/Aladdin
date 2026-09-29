## Summary

Describe the user or system outcome and why this change is needed.

## Change Type

- [ ] Feature
- [ ] Bug fix
- [ ] Infrastructure / CI/CD
- [ ] Documentation
- [ ] Maintenance

## Areas Changed

- [ ] Frontend
- [ ] Backend API
- [ ] Worker / agent pipeline
- [ ] Database
- [ ] Containers / deployment
- [ ] Documentation only

## Validation

List every command run and its result.

```text
command -> result
```

## Contract and Deployment Impact

State any changes to APIs, schemas, Dockerfiles, ports, health checks, environment variables, Compose services, volumes, or deployment steps. Write `None` if there is no impact.

## Screenshots or API Examples

Add evidence for UI or API behavior when applicable.

## Rollback

Explain how to reverse this change. Write `Revert this pull request` when no additional rollback action is required.

## Checklist

- [ ] This pull request targets `develop`, is a release from `develop` to `main`, or is the one-time branch bootstrap pull request.
- [ ] The change has one focused outcome.
- [ ] Tests cover the changed behavior.
- [ ] Local lint, tests, and builds pass for affected components.
- [ ] Documentation and API contracts are updated.
- [ ] No secret, `.env` file, token, or connection string is committed.
- [ ] Deployment and configuration impact is documented.
- [ ] I notified the CI/CD owner about container contract changes, or this pull request does not change the container contract.
