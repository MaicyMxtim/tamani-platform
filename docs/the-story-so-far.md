# The Tamani Platform — what we've built so far

This is a plain walkthrough of everything done on the project between 22 and 23 July 2026. It is written for someone new to this field. Technical words are shown in **bold** and explained the first time they appear.

---

## 1. What we are building and why

You already have a venue discovery app. It has a database of 1,275 real restaurants, cafés and bars in Brighton. Each venue is tagged with "vibes" such as *late-night* or *work-friendly*.

This project takes that data and builds professional **infrastructure** around it. Infrastructure means all the systems that keep software running reliably: the servers, the deployment process, the security, the monitoring.

The app itself is not the point. The infrastructure is the point. Platform engineering, DevOps, cloud and SRE jobs are all about this kind of work, and this project gives you real evidence that you can do it. When it is finished, the GitHub repository will show working examples of the skills those jobs ask for.

Three basic words before we start:

- A **server** is a computer that runs your software and answers requests from other computers. It can be your laptop or a rented machine in a data centre.
- An **API** is a program that answers structured questions over the internet. When an app asks "give me all the late-night venues", the API is the program that answers.
- **Production** (or "prod") is the live environment that real users touch. **Development** ("dev") is your private practice area. Breaking dev is normal. Breaking production is a problem.

---

## 2. The three programs we wrote

The whole system is built around three small Python programs.

**The API** serves the venue data. It handles search, filtering, and a feed. It is built with **FastAPI**, a popular Python tool for writing APIs.

**The inference gateway** will be the only program allowed to talk to an AI model. Every AI request in the system has to go through this one door. That is how you control spending, cache repeated answers, and keep API keys in one place. **Inference** simply means asking a trained AI model a question. Right now the gateway uses a fake classifier that costs nothing. We will connect a real AI model in Phase 5.

**The worker** does background jobs. When a job like "classify venue X" appears on a queue, the worker picks it up, calls the gateway, and saves the result. Workers exist so that slow tasks never block the API. The API answers users straight away, and the heavy work happens in the background.

---

## 3. Phases 0 and 1: containers

### The problem containers solve

There is an old joke in software: "it works on my machine". Code often behaves differently on a server than on your laptop, because the two machines have different versions of Python, different libraries, and different settings.

A **container** solves this. It packages a program together with everything it needs: the right Python version, the right libraries, the right system files. The result runs the same way on any computer. **Docker** is the standard tool for building and running containers.

Two related words: an **image** is the frozen, shippable version of a container, like a recipe that has been prepared and boxed. A container is an image that is actually running. A **Dockerfile** is the text file that describes how to build the image.

We used a technique called a **multi-stage build**. The tools needed to build the program are used in a temporary stage and then thrown away, so the final image only contains what is needed to run. Smaller images download faster, and they give attackers less to work with.

### Security hardening

We made the containers deliberately restrictive:

- **Non-root.** Inside each container, our program runs as a low-privilege user instead of the all-powerful "root" account. If an attacker gets in, they land in a locked room rather than the control tower.
- **Read-only filesystem.** The running program cannot change its own files.
- **Health probes.** These are small web addresses that the platform checks to ask "are you OK?". There are three kinds, and they answer different questions. The **liveness** probe asks "is the process responding at all?" If not, restart it. The **readiness** probe asks "are you ready for traffic right now?" It checks things like whether the database is reachable. If not, hold traffic back, but do not restart. The **startup** probe asks "are you still booting?" Mixing these up is a classic mistake. If your database goes down and your liveness probe checks the database, Kubernetes will restart your app over and over, which fixes nothing.
- **Structured logging.** Every log line is written as JSON so machines can search it. Every request also gets a random **correlation ID** that follows it from service to service. When something breaks, you can search for that one ID and see the whole journey of a single request.

### Running everything locally

**Docker Compose** starts many containers together from one configuration file. One command brings up our three programs plus the supporting services:

- **Postgres** is a database. It is the long-term memory of the system.
- **Redis** is a very fast, temporary data store. We use it for caching and counters. If Postgres is a filing cabinet, Redis is the sticky notes on your desk.
- **NATS** is a message queue. Phase 4 covers it properly.
- **Prometheus** collects **metrics**, which are numbers tracked over time, like requests per second or memory used. It visits each service every 15 seconds and records what it finds.
- **Grafana** turns those numbers into dashboards and charts.

We also wrote a **Makefile**, which is a list of command shortcuts. `make up` starts everything. `make test` runs the tests. `make smoke` checks that every service answers. This means nobody has to memorise long commands.

### Version control and the data

Everything lives in **Git**, the standard tool for tracking changes to code. It records every change, who made it, and why. Our project is a **monorepo**, which means one repository holds everything: the apps, the infrastructure files, and the documentation. It is published on GitHub as `MaicyMxtim/tamani-platform`.

You asked not to use the original app's live machinery, because it calls paid services. So we took a **static snapshot** instead: the 1,275 venues were exported once into a file, and that file is baked into the API's image. Real data, no ongoing costs. Of those venues, 1,231 already have vibe tags and 44 do not. Those 44 will be the first real job for the AI enrichment agent later.

---

## 4. Phase 2: Kubernetes

### What Kubernetes is

Docker runs one container. **Kubernetes** runs many containers across one or more machines, and keeps them running. You give it a written description of what you want, for example "run two copies of the API, give each this much memory, restart them if they crash". Kubernetes then works constantly to make reality match that description.

This style is called **declarative**. You declare the destination, and the system works out the driving directions.

The main vocabulary:

- A **cluster** is a group of machines that Kubernetes manages as one unit.
- A **node** is one machine in the cluster.
- A **pod** is the smallest unit Kubernetes runs. It is usually one container.
- A **deployment** tells Kubernetes "keep this many copies of this pod running", and manages upgrades.
- A **service** gives pods a stable internal name, like `tamani-api`. Pods come and go, but the name always works.
- A **namespace** is a partition inside a cluster. We made three: dev, staging and prod, so the environments cannot interfere with each other.
- **kubectl** is the command-line tool for giving instructions to a cluster.

We run two clusters. **minikube** is a practice cluster that lives entirely on your Mac. **k3s** is a lightweight but real Kubernetes that runs on our rented cloud machine.

### The guardrails

Anyone can install Kubernetes. The rarer skill, and the one this phase demonstrates, is making one cluster safe for several teams and environments to share. We built:

- **RBAC**, which stands for role-based access control. It defines who may do what. We created a "developer" role that can read pods and logs but cannot delete anything, and a "deployer" role that can update workloads and nothing else. We tested this by asking the cluster directly, and it refused the forbidden actions.
- **Resource quotas.** Each namespace has a cap on how much CPU, memory and how many pods it can use. Without caps, one runaway service can starve everything else on the cluster.
- **Network policies.** These are firewalls between pods. We started with "deny everything", and then opened only the specific connections the design needs. For example, the worker may talk to the gateway, but the API may not. We proved this live: a blocked connection failed, an allowed one worked. One well-known trap: "deny everything" also blocks **DNS**, the phonebook service that turns names into network addresses. You have to re-allow DNS explicitly or nothing in the namespace can find anything.
- **Pod Security.** The cluster refuses any pod that asks for dangerous privileges, such as running as root.
- **Kyverno**, an **admission controller**. This is a doorman that inspects everything entering the cluster and rejects anything that breaks the rules, before it runs. Our rules: no `latest` image tags, every container must declare memory and CPU limits, and every deployment must be labelled. We tested it by trying to run a rule-breaking pod, and the cluster refused it with a written explanation.

Why is the `latest` tag banned? Image tags are like stickers, and `latest` gets moved to each new image as it is built. A pod that says "run latest" might run different code every time it restarts, and you can never be sure what is actually deployed. Pinning an exact version removes the guesswork.

---

## 5. Renting a real computer: AWS and Terraform

### What we rented

"The cloud" means renting computers in someone else's data centre. **AWS** (Amazon Web Services) is the largest provider. We set up:

- An **EC2 instance**, which is one virtual machine. Ours is a small one (2 CPUs, 2 GB of memory) in the London region. It runs our k3s cluster.
- An **Elastic IP**, which is a permanent public address for the machine.
- **Route53**, which is AWS's **DNS** service. DNS is the internet's phonebook. It translates `platform.waypear.com` into the machine's numeric address. You updated your domain registrar to hand DNS control to AWS. That is what the four "awsdns" nameserver entries were for.
- An **S3 bucket**, which is cheap file storage. Ours holds backups, and automatically deletes anything older than 30 days.
- A **security group**, which is AWS's firewall around the machine. Web traffic is open to everyone. Remote login and cluster control are only allowed from your home IP address.

**SSH** is the standard way to log into a remote machine. It uses a **key pair**: two mathematically linked files. The public half sits on the server. The private half stays on your Mac and proves you are you. There is no password to steal.

### Infrastructure as code

We did not click any of this together in the AWS website. We described it all in **Terraform**, a language for defining cloud infrastructure in text files, and then ran one command to make AWS match the description.

This approach is called **infrastructure as code**, and it matters for three reasons. The files live in Git, so infrastructure changes have history and can be reviewed. The whole setup can be rebuilt from scratch. And you can detect **drift**, which is when the real world quietly stops matching the written description. We checked for drift after building, and the answer was "no changes", which is exactly what you want.

Two small notes. We actually use **OpenTofu**, a free open-source version of Terraform, because the original changed its licence. They work identically. And to answer your question from that evening: the tool is free. What costs money are the AWS resources it creates. Your new-account free credits are currently covering the machine, and DNS costs about 50p a month.

---

## 6. Phase 3: GitOps

### The idea

The traditional way to deploy software is for a person to log into a server and run commands. It works until someone forgets a step, or nobody remembers what was done six months ago.

**GitOps** flips this around. The Git repository becomes the single source of truth for what should be running. Software inside the cluster reads the repository and makes reality match it. To change production, you change a file, commit it, and push. Every deployment in history is visible in the Git log.

Two automated systems make this work.

**GitHub Actions** provides **CI**, which stands for continuous integration. Every time code is pushed, a robot runs the tests. If they pass, it builds the three container images and uploads them to **GHCR**, GitHub's image storage. This is the "registry" we dealt with when the cluster could not download the images. The images were stored privately, and the cluster had no credentials, so you made them public.

**Argo CD** runs inside the cluster. It constantly compares what Git says should exist with what actually exists, and fixes any difference. It reads our repository using a **deploy key**, which is a key that grants read-only access to that one repository and nothing else.

### One file bootstraps everything

We used a pattern called **app of apps**. I applied exactly one file to the cluster by hand: a "root" application. That root defines all the other applications, and Argo creates and manages them itself. Everything since then has entered the cluster through Git only.

Different environments get different trust levels. Platform configuration syncs automatically. Production workloads sit behind a **manual gate**: a human has to consciously approve each release. Promoting to production is a deliberate act, which is exactly what the project plan asks for.

Production also pins its images by **commit SHA**. A SHA is the unique fingerprint of one exact Git commit. Pinning by SHA means you can always answer the question "exactly what code is running in production right now?"

### The front door

To let the public reach the cluster safely, we added:

- **ingress-nginx**, the cluster's front door. An **ingress** is a routing rule, such as "requests for platform.waypear.com go to the API service". Ours also limits each visitor to 20 requests per second as a basic defence.
- **cert-manager** with **Let's Encrypt**. **TLS** is the encryption behind the padlock in your browser, the S in HTTPS. Certificates prove a website is who it claims to be. Let's Encrypt issues them for free, and cert-manager is the robot that requests and renews them automatically. Our certificate was issued 44 seconds after we asked, because your DNS change had already taken effect.

The result is live right now. **https://platform.waypear.com** serves your venues to the whole internet, encrypted, from your own cluster, deployed entirely from Git. The page at `/docs` is an interactive explorer where you can try the API in your browser.

---

## 7. Phase 4: the message queue, done properly

### Why queues exist

Some work does not need an instant answer. "Reclassify all 1,300 venues" is a good example. You do not do that kind of work inside an API request. Instead you put messages on a **queue**, and workers process them at their own pace. The API stays fast. If a worker dies, the messages simply wait.

Our message system is **NATS JetStream**. Its concepts:

- A **stream** is a durable log of messages, saved to disk, which survives restarts.
- A **subject** is a message's address. Ours are hierarchical, like `venue.enrichment.requested` and `venue.enrichment.completed`, so a program can subscribe to exactly the kind it cares about.
- A **consumer** is a reader's bookmark in the stream. Our workers share one bookmark as a group, so each message is handled by exactly one worker, even when there are many workers.

We also wrote an **ADR**, an architecture decision record. It is a short document explaining why we chose NATS instead of the two obvious alternatives, Kafka and Redis Streams. Kafka is the industry standard but is far too heavy for our small machine. Redis Streams was already installed but gives weaker guarantees. ADRs prove that decisions were made with reasons, not by default.

### Handling failure

The hard part of messaging is what happens when things fail. Here is what we built, and every one of these was demonstrated with a real test, not just written down:

**Messages can arrive twice.** Our system guarantees each message is delivered at least once, which sometimes means more than once. So every worker is **idempotent**, which means doing the same job twice causes no harm. Each message carries an ID, and the worker checks "have I already finished this one?" before working.

We found a real bug here. My first version marked a job as done *before* doing the work. That looks harmless, but think about a worker that crashes in the middle of a job. The "done" marker is already written, so when the message is redelivered, the next worker skips it. The work is silently lost. The fix is to check at the start but only write the marker after the job succeeds.

**Workers only confirm after finishing.** A worker tells the queue "delete this message" only when the work is complete. We proved the value of this by force-killing a worker 12 seconds into a job. The message was automatically given to a healthy worker, which finished it. Nothing was lost.

**Failed messages retry with growing delays.** A failing message is retried after 1 second, then 2, then 4, then 8. This spacing is called **exponential backoff**, and it stops a struggling service from being hammered by instant retries. We watched these exact delays appear in the logs.

**Hopeless messages go to a dead letter queue.** After 5 failed attempts, a message is moved to a separate **DLQ** subject where a human can inspect it. Without this, a broken message would retry forever.

**Garbage goes to quarantine.** A message that is not even valid data would crash every worker that touched it, over and over, and take down the whole pool. This is called a **poison message**. Our worker detects it immediately and parks it in a quarantine subject without retrying. We tested this by feeding the system deliberate garbage, and the workers carried on unharmed.

**History can be replayed.** Because the stream keeps its history, a small script can re-send all messages from any point in time. This is how you redo work after improving the classifier.

**The backlog is measured.** The number of waiting messages is called **consumer lag**, and we publish it as a metric. Later it becomes the signal for **autoscaling**: when the backlog grows, add workers; when it empties, remove them.

---

## 8. The night we broke production

During the Phase 4 release, the website went down for about ten minutes. This was our first real **incident**, and honestly, it is one of the most valuable things in the project so far. The plan itself says that most job candidates have never diagnosed a system they own, because they have never broken one.

Here is what happened, step by step.

Our cloud machine has 2 GB of memory, and normal usage was already close to the limit. When Kubernetes upgrades an application, it briefly runs the old and new copies side by side. On top of that, the machine was unpacking three freshly downloaded images. Together this pushed memory demand past what the machine had.

The machine also had no **swap**. Swap is space on disk that acts as slow overflow memory. Without it, the machine entered a state called **thrashing**: it spent all its effort shuffling memory around and had nothing left for real work. The clue that told us this: SSH would accept a connection, but could not actually run any command. The machine was not dead. It was overwhelmed.

The fix, in order: we rebooted the machine through AWS, which was safe because everything on it can be rebuilt from Git. We added 2 GB of swap so this failure mode cannot lock the machine again. And we changed the upgrade strategy so new pods replace old ones one at a time instead of doubling up. The trade-off is a few seconds of downtime per service during each release, which is acceptable for now.

There were two deeper lessons.

First, a green status light is not proof. During the chaos, Argo reported the release as "Healthy" and "Synced" while it had actually applied old files from its cache. We only caught this by checking which image was truly running, and it was the old one. The lesson: verify the thing itself, not the dashboard about the thing.

Second, every fix went back into code. The swap setup is now part of the machine's build script, so a replacement machine gets it automatically. The upgrade strategy fix is in the deployment configuration. And the whole event is written up as a **postmortem**, the industry's standard incident report. Postmortems are "blameless": they ask why the system allowed the failure, not whose fault it was. Ours lives in the repository under `runbooks/postmortems/`.

---

## 9. Phase 5: the gateway becomes real

This phase connected a real AI model. You created an API key at Anthropic and stored it in two places: a local file that Git ignores, and a Kubernetes **secret**, which is the cluster's built-in store for sensitive values. Secrets never go into Git.

The gateway now works like this. A request comes in. First it checks the tenant's **token budget**, which is a spending allowance per minute and per day. A tenant that runs out gets told to retry later instead of running up a bill. Then it checks the **semantic cache**. The venue description is turned into an **embedding**, which is a list of numbers that captures the meaning of the text. If a previous request was similar enough, the stored answer is returned for free. Only if there is no match does the gateway call Claude, and the response comes back in a guaranteed valid format because we use the API's structured output feature.

We tuned the cache threshold with real data instead of guessing. Across 400 real venues, a threshold of 0.94 produced zero wrong cache answers in our sample. A looser threshold would save more money but sometimes serve a cached answer that did not really fit. We chose accuracy.

Real numbers from the first live runs: one classification costs about $0.004, so a thousand cost about $3.92. We classified all 44 venues that had no tags for a total of $0.18. The model marked 43 of them as low confidence, which is honest: those venues only have a name and a type to go on. In Phase 6 those low-confidence answers will go to a human review queue instead of being written to the database as truth.

Deploying to production found three real problems, which is normal and useful. First, our locked-down containers have read-only filesystems, and the embedding library needed one small scratch folder, so we gave it exactly that and nothing more. Second, our firewall rules blocked the gateway from reaching Anthropic at all, because in Phase 2 we had denied everything by default. We opened one specific path: the gateway, and only the gateway, may make outbound encrypted calls. Third, and most interesting: while the key was misconfigured, the gateway correctly fell back to its free mock classifier, but those mock answers were being saved into the cache and kept being served after the real provider came back. The fix is a rule that fallback answers are never cached. Finding that bug before it mattered is exactly what this project is for.

We also upgraded the cloud machine from 2 GB to 4 GB of memory, since the incident in Phase 4 proved the small one was full. It costs about $34 a month, covered by your AWS credits for now.

## 10. Phases 6 to 11: the rest of the build

**Phase 6, governed agents.** This is the flagship. We built two AI agents that act on their own, made safe by a set of controls. Each agent has a **capability manifest**: a list of the only tools it is allowed to use, and anything outside that list is refused. Each has spending caps, a time limit, and a limit on how many actions it can take before it must stop. It has **loop detection**, which halts an agent that keeps repeating the same action. It has a **dry-run mode** that simulates every action without actually doing it. We proved all of these by trying to break the rules and watching the system refuse.

The first agent classifies venues and sends any low-confidence answer to a human review queue instead of saving it. The second is an operations agent. You labelled a **golden set** for us, a couple of hundred venues judged by a human, and that became the yardstick every AI change is measured against. The operations agent reads a production alert, investigates the cluster using read-only access it cannot exceed, works out the cause, and **opens a pull request with its diagnosis**. It never changes anything itself. We proved it live: we deliberately broke a pod, and the agent opened a correct pull request diagnosing exactly what was wrong.

**Phase 7, observability.** We deployed the monitoring stack: Prometheus for metrics, Grafana for dashboards, Loki for logs. We defined **SLOs**, which are formal reliability targets, such as "99.5% of requests succeed" and "95% of requests are faster than 400 milliseconds". We added **burn-rate alerts**: a fast problem pages immediately, a slow problem raises a ticket, which cuts out most alert noise. You saw the live dashboards showing 100% availability and 95-millisecond response times.

**Phase 8, supply chain security.** Every image is now **signed** during the build using a signature tied to this repository, not a password that could leak. The cluster refuses any image that is not signed, which we proved by trying to run an unsigned one and getting rejected. Every build is also scanned for known vulnerabilities and ships an ingredient list called an **SBOM**. The API key moved out of the cluster into AWS's secret store, from where it syncs in automatically.

**Phase 9, reliability proof.** We ran load tests and deliberate failure experiments, each with a written prediction beforehand. Killing an API copy under live traffic caused zero errors. Killing the single AI gateway caused a 20-second gap that recovered on its own. We also found the platform's breaking point: around 25 to 30 simultaneous users, the small shared machine runs out of memory. Rather than hide that, we documented it honestly, which is exactly the kind of evidence the plan says employers look for. The project now has three real incident write-ups.

**Phase 10, developer self-service.** This is what makes it a true internal developer platform. One command, `tamani new`, creates a complete new service with everything already wired in: hardened container, health checks, monitoring, security policy, a signed build pipeline, and a runbook. We measured it end to end: **195 seconds from the command to the new service answering live traffic**, with no manual cluster work. A developer here cannot ship a service without proper operability, because the template supplies it all.

**Phase 11, cost and unit economics.** We put a real money figure on everything. A thousand classifications cost about $4 on the best model. We ran an experiment comparing three models of different price and quality against your golden set, and found that using a cheaper model for easy cases and the expensive one only for hard cases would cut cost by about 57% for a small, measured drop in accuracy. We also worked out that self-hosting the AI would only pay off at hundreds of thousands of classifications a month, far above what this app needs, so the managed service is the right call. All of it is written up in `docs/unit-economics.md`.

## 11. The build is complete

All twelve phases are done. You have a live, public, encrypted website running on your own Kubernetes cluster on AWS, deployed entirely through Git, with a governed AI system, full monitoring, an enforced secure supply chain, three genuine incident write-ups, a one-command service generator, and published cost figures. Total spend: your free AWS credits, a few dollars of AI usage, and about 50p a month for DNS.

The repository tells a story most portfolios cannot: real production, a real outage handled and learned from, real reliability targets, real AI agents kept safe, and real money figures. That is the whole point of the project.

---

## 11. Quick reference

| Term | Meaning |
|---|---|
| API | A program that answers structured requests over the internet |
| Container | A program packaged with everything it needs, so it runs the same everywhere |
| Image | The frozen, shippable form of a container |
| Docker | The standard tool for building and running containers |
| Kubernetes | Software that keeps many containers running to match a written description |
| Pod | The smallest unit Kubernetes runs, usually one container |
| Deployment | An instruction to keep a number of pod copies running |
| Namespace | A partition inside a cluster, like dev, staging and prod |
| RBAC | Rules for who may do what in the cluster |
| Network policy | A firewall between pods |
| Kyverno | A doorman that rejects rule-breaking workloads before they run |
| Terraform | A language for defining cloud infrastructure in text files |
| Drift | When reality stops matching the written definition |
| DNS | The internet's phonebook, turning names into addresses |
| TLS | The encryption behind the browser padlock |
| CI | A robot that tests and builds your code on every push |
| Registry | Storage for built container images |
| GitOps | Git is the source of truth, and software syncs the cluster to it |
| Argo CD | The tool that does GitOps in our cluster |
| Ingress | Rules for routing outside traffic into the cluster |
| Queue | A place where jobs wait until a worker picks them up |
| Idempotent | Safe to run twice |
| Exponential backoff | Growing delays between retries |
| Dead letter queue | A parking area for messages that keep failing |
| Poison message | A broken message that would crash workers forever |
| Consumer lag | The size of the message backlog |
| Swap | Disk space used as slow overflow memory |
| Thrashing | A machine so short of memory it can do no useful work |
| Postmortem | A blameless report on an incident and its lessons |
| ADR | A short record of why a technical decision was made |

*This document lives in the repository at `docs/the-story-so-far.md` and will grow with the project.*
