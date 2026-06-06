\# TimesFM-HPA Helm Chart



Install TimesFM-HPA as a drop-in Kubernetes plugin.



\## Installation



```bash

helm install my-autoscaler ./charts/timesfm-hpa \\

&#x20; --set image.tag=v2 \\

&#x20; --set targetDeployment.name=my-app \\

&#x20; --set controller.minReplicas=1 \\

&#x20; --set controller.maxReplicas=10

```



\## Configuration



See `values.yaml` for all configurable parameters. Key options:



| Parameter                    | Description                                  | Default      |

|------------------------------|----------------------------------------------|--------------|

| `image.tag`                  | Container image tag                          | `v2`         |

| `targetDeployment.name`      | Name of the Deployment to scale              | `autoscaler-plugin` |

| `controller.minReplicas`     | Minimum replica count                        | `1`          |

| `controller.maxReplicas`     | Maximum replica count                        | `2`          |

| `controller.loopIntervalSeconds` | Control loop interval                    | `60`         |

| `controller.targetUtilization` | Target CPU utilization for scaling decisions | `0.5`      |

| `controller.prometheusUrl`   | Prometheus endpoint URL                      | (in-cluster) |



\## Uninstall



```bash

helm uninstall my-autoscaler

```

