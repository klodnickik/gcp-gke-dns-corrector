#!/bin/bash
docker build -t  eu.gcr.io/krzysiek-master-project/gcp-gke-dns-corrector:1.0 .
docker push eu.gcr.io/krzysiek-master-project/gcp-gke-dns-corrector:1.0
