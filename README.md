# Oracle Cloud A1.Flex Auto-Creator

> Automatically provision Oracle Cloud's free VM.Standard.A1.Flex instance (4 OCPU / 24 GB RAM) using GitHub Actions — runs 24/7 without your laptop.

![Oracle Cloud](https://img.shields.io/badge/Oracle%20Cloud-Free%20Tier-red)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-blue)
![Python](https://img.shields.io/badge/Python-3.11-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What This Does

Oracle Cloud's Always Free tier includes a powerful ARM instance:

| Spec | Value |
|------|-------|
| **Shape** | `VM.Standard.A1.Flex` |
| **CPU** | 4 OCPU (Ampere ARM) |
| **RAM** | 24 GB |
| **Boot Volume** | 200 GB (total across all instances) |
| **Cost** | $0 forever |

The catch? **It's always out of capacity.** Thousands of users compete for the same free slots. This project solves that by polling Oracle's API every 10 minutes — 24/7, running on GitHub's infrastructure — and instantly grabs an instance the moment capacity frees up.

---

## How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  GitHub Actions │────▶│  OCI Python  │────▶│  Oracle Cloud   │
│  Every 10 min   │     │  SDK + API   │     │  Create Instance│
└─────────────────┘     └──────────────┘     └─────────────────┘
         │                                              │
         │◀─────────────────────────────────────────────┘
         │           Out of capacity? → Retry in 10 min
         │           Success? → 🎉 Notify & stop
         │
         ▼
    Discord / Telegram
    (optional notification)
```

**Why this works:**
- No infinite loop → no rate limit issues
- Each run is spaced 10 minutes apart → Oracle's API is happy
- GitHub Actions runs 24/7 → no laptop needed
- Completely free (within 2,000 GitHub minutes/month)

---

## Quick Start

### 1. Fork or Create This Repo

Click **"Use this template"** or create a new repo and push these files.

### 2. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Description | Where to Find |
|--------|-------------|---------------|
| `OCI_USER_OCID` | Your OCI user ID | Profile → User Settings → Copy OCID |
| `OCI_TENANCY_OCID` | Your tenancy ID | Same as Compartment ID for root |
| `OCI_FINGERPRINT` | API key fingerprint | Profile → API Keys → looks like `aa:bb:cc:dd...` |
| `OCI_PRIVATE_KEY` | Full `.pem` private key | Open your `.pem` file, copy ALL text |
| `OCI_REGION` | Your region | e.g., `ap-hyderabad-1` |
| `OCI_COMPARTMENT_ID` | Compartment OCID | Usually same as Tenancy OCID |
| `OCI_AVAILABILITY_DOMAIN` | Full AD name | Console → Administration → ADs |
| `OCI_SUBNET_ID` | Subnet OCID | Networking → VCN → Subnets |
| `OCI_IMAGE_ID` | ARM (aarch64) image OCID | Must be ARM-compatible for A1.Flex |
| `SSH_PUBLIC_KEY` | Your SSH public key | `~/.ssh/id_rsa.pub` |

**Optional notifications:**
| Secret | Description |
|--------|-------------|
| `DISCORD_WEBHOOK_URL` | Discord webhook for success notifications |
| `TELEGRAM_TOKEN` | Telegram bot token (@BotFather) |
| `TELEGRAM_USER_ID` | Your Telegram user ID (@myidbot) |

### 3. Enable the Workflow

1. Go to **Actions** tab
2. Click **"Enable workflows"** if prompted
3. Click **"Oracle A1.Flex Instance Creator"**
4. Click **"Run workflow"** → **"Run workflow"**

### 4. Wait & Watch

The workflow runs automatically every 10 minutes. Check the logs to see:
- `Out of capacity (500)` → Normal, will retry
- `Rate limited (429)` → Also normal, will retry
- `SUCCESS! Instance created` → 🎉 You got it!

### 5. After Success

1. **Disable the workflow** → Actions → Disable (stops burning minutes)
2. SSH into your instance: `ssh -i ~/.ssh/id_rsa ubuntu@<PUBLIC_IP>`
3. Optionally delete this repo (or keep it for future use)

---

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── oracle-a1-creator.yml    # GitHub Actions workflow (runs every 10 min)
├── github_actions_oracle_a1.py     # Main Python script (one-shot creator)
├── README.md                        # This file
├── LICENSE                          # MIT License
└── .gitignore                       # Ignore sensitive files
```

---

## Architecture

### Why One-Shot Instead of Infinite Loop?

| Approach | Problem | This Solution |
|----------|---------|---------------|
| Infinite loop on laptop | Laptop must stay on, rate limits after 30s | GitHub Actions runs 24/7 |
| Infinite loop on server | Need a server first, rate limits from aggressive retry | 10-minute spacing = no rate limits |
| Manual clicking | Impossible to catch capacity drops | Automated, always watching |

### Exit Codes

The script returns specific exit codes so GitHub Actions knows what happened:

| Code | Meaning | Action |
|------|---------|--------|
| `0` | Success! Instance created | 🎉 Stop workflow, send notification |
| `1` | Out of capacity | Retry in next scheduled run |
| `2` | Rate limited (429) | Retry in next scheduled run |
| `3` | Config/auth error | Needs manual fix |
| `4` | Unexpected error | Will retry |

---

## Free Tier Limits

**GitHub Actions:**
- Public repos: 2,000 minutes/month
- This workflow: ~144 runs/day × 30 days = ~4,320 runs/month
- Each run: ~5-30 seconds on failure
- Total: ~360-720 minutes/month ✅ well within limits

**Oracle Cloud Always Free:**
- 4 OCPU + 24 GB RAM total across all A1 instances
- 200 GB boot volume total
- 10 TB outbound data/month
- 1 load balancer (10 Mbps)

---

## Security

- **Secrets are never in code** — they live in GitHub's encrypted Secrets store
- **Private keys are not committed** — `.gitignore` prevents accidental commits
- **No hardcoded credentials** — all values come from environment variables
- **Public repo is safe** — secrets are injected at runtime, never visible

---

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `401 NotAuthenticated` | Bad fingerprint or private key | Check `OCI_FINGERPRINT` and `OCI_PRIVATE_KEY` secrets |
| `404 NotAuthorizedOrNotFound` | Wrong compartment or subnet OCID | Verify OCIDs in Oracle Console |
| `400 InvalidParameter` | Image is x86, not ARM | Use an `aarch64` (ARM) image for A1.Flex |
| `Out of capacity` forever | Region permanently full | Try a different region (new account) |
| `429 Too many requests` | Even 10 min is too fast | Increase interval to 15 min in workflow YAML |

---

## FAQ

**Q: Is this against Oracle's Terms of Service?**
A: No. This uses the official OCI Python SDK and public API, exactly as documented. It simply automates the same "Create Instance" button you'd click manually.

**Q: Will I get charged?**
A: No — as long as you stay within Always Free limits (4 OCPU, 24 GB RAM, 200 GB storage). Set up budget alerts in Oracle Console just to be safe.

**Q: How long does it take?**
A: It depends entirely on your region's capacity. Some users get it in hours, others wait days or weeks. High-demand regions like US Ashburn are often permanently full. Less popular regions like Frankfurt or Jeddah sometimes have better availability.

**Q: Can I run this for multiple regions?**
A: Yes — duplicate the workflow file and change the region/AD/image values. But you need a separate Oracle account per region (Oracle locks your home region at signup).

**Q: What happens after the instance is created?**
A: The script sends a notification (if configured) and exits. The workflow keeps running but the script sees the instance already exists and does nothing. You should disable the workflow to stop burning GitHub minutes.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

> Built with ❤️ for the free tier community. Good luck snagging that A1 instance! 🚀
