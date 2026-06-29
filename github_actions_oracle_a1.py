#!/usr/bin/env python3
"""
Oracle Cloud A1.Flex One-Shot Creator
=======================================
Tries to create the VM.Standard.A1.Flex instance ONCE.
Designed for GitHub Actions (runs every 5 minutes via cron schedule).

Exit codes:
    0 = Instance created successfully (or already exists)
    1 = Out of capacity (will retry on next GitHub Actions run)
    2 = Rate limited 429 (will retry on next run)
    3 = Config/auth error (needs manual fix)
    4 = Unexpected error (will retry on next run)

Environment variables (set via GitHub Secrets):
    OCI_USER_OCID          - Your OCI User OCID
    OCI_TENANCY_OCID       - Your OCI Tenancy OCID
    OCI_FINGERPRINT        - API Key fingerprint
    OCI_PRIVATE_KEY        - Full contents of your .pem private key
    OCI_REGION             - e.g., ap-hyderabad-1
    OCI_COMPARTMENT_ID     - Compartment OCID (usually = tenancy OCID)
    OCI_AVAILABILITY_DOMAIN - Full AD name, e.g., Cwfi:AP-HYDERABAD-1-AD-1
    OCI_SUBNET_ID          - Subnet OCID
    OCI_IMAGE_ID           - ARM image OCID
    SSH_PUBLIC_KEY         - Contents of your SSH public key
    
Optional notifications (also via GitHub Secrets):
    DISCORD_WEBHOOK_URL    - Send success message to Discord
    TELEGRAM_TOKEN         - Telegram bot token
    TELEGRAM_USER_ID       - Your Telegram user ID
"""

import os
import sys
import traceback
from datetime import datetime

# ---------------------------------------------------------------------------
#  CONFIGURATION — reads from environment variables (GitHub Secrets)
# ---------------------------------------------------------------------------

def get_env(name, required=True):
    val = os.environ.get(name, "")
    if required and not val:
        print(f"ERROR: Missing required environment variable: {name}")
        sys.exit(3)
    return val

# OCI Config (built from env vars instead of file)
OCI_USER_OCID = get_env("OCI_USER_OCID")
OCI_TENANCY_OCID = get_env("OCI_TENANCY_OCID")
OCI_FINGERPRINT = get_env("OCI_FINGERPRINT")
OCI_PRIVATE_KEY = get_env("OCI_PRIVATE_KEY")
OCI_REGION = get_env("OCI_REGION")

COMPARTMENT_ID = get_env("OCI_COMPARTMENT_ID")
AVAILABILITY_DOMAIN = get_env("OCI_AVAILABILITY_DOMAIN")
SUBNET_ID = get_env("OCI_SUBNET_ID")
IMAGE_ID = get_env("OCI_IMAGE_ID")
SSH_PUBLIC_KEY = get_env("SSH_PUBLIC_KEY")

SHAPE = "VM.Standard.A1.Flex"
OCPUS = 4  # or 2 if you want to split across 2 instances
MEMORY_IN_GBS = 24  # or 12 if splitting
BOOT_VOLUME_SIZE = 50
DISPLAY_NAME = "free-tier-arm-a1"

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_USER_ID", "")

# ---------------------------------------------------------------------------


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def send_discord(message):
    if not DISCORD_WEBHOOK:
        return
    try:
        import requests
        requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    except Exception as e:
        log(f"Discord notification failed: {e}")


def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_USER_ID:
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_USER_ID, "text": message}, timeout=10)
    except Exception as e:
        log(f"Telegram notification failed: {e}")


def notify(message):
    log(message)
    send_discord(message)
    send_telegram(message)


def build_oci_config():
    """Build OCI config dict from environment variables."""
    return {
        "user": OCI_USER_OCID,
        "tenancy": OCI_TENANCY_OCID,
        "fingerprint": OCI_FINGERPRINT,
        "key_content": OCI_PRIVATE_KEY,
        "region": OCI_REGION,
    }


def create_instance(compute_client, network_client):
    """Attempt to create the A1.Flex instance."""
    import oci

    instance_details = oci.core.models.LaunchInstanceDetails(
        availability_domain=AVAILABILITY_DOMAIN,
        compartment_id=COMPARTMENT_ID,
        shape=SHAPE,
        display_name=DISPLAY_NAME,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=OCPUS,
            memory_in_gbs=MEMORY_IN_GBS,
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=IMAGE_ID,
            boot_volume_vpus_per_gb=120,
            boot_volume_size_in_gbs=BOOT_VOLUME_SIZE,
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True,
            display_name=f"{DISPLAY_NAME}-vnic",
        ),
        metadata={
            "ssh_authorized_keys": SSH_PUBLIC_KEY,
        },
        is_pv_encryption_in_transit_enabled=False,
    )

    response = compute_client.launch_instance(instance_details)
    instance = response.data
    log(f"SUCCESS! Instance created: {instance.id}")
    log(f"  Name: {instance.display_name}")
    log(f"  AD:   {instance.availability_domain}")
    log(f"  State: {instance.lifecycle_state}")
    return instance


def wait_for_running(compute_client, instance_id):
    """Wait until instance is RUNNING and return public IP."""
    import oci

    log("Waiting for RUNNING state...")
    for _ in range(30):  # max 5 minutes
        instance = compute_client.get_instance(instance_id).data
        state = instance.lifecycle_state
        log(f"  State: {state}")
        if state == "RUNNING":
            break
        if state in ("TERMINATED", "TERMINATING"):
            log("ERROR: Instance terminated.")
            return None
        import time
        time.sleep(10)

    # Get public IP
    vnic_attachments = compute_client.list_vnic_attachments(
        compartment_id=COMPARTMENT_ID,
        instance_id=instance_id,
    ).data

    for vnic_att in vnic_attachments:
        try:
            import oci
            vnic = oci.core.VirtualNetworkClient(build_oci_config()).get_vnic(vnic_att.vnic_id).data
            if vnic.public_ip:
                return vnic.public_ip
        except:
            pass

    return None


def is_capacity_error(error):
    msg = str(error).lower()
    return any(phrase in msg for phrase in [
        "out of capacity", "out of host capacity", "capacity", "no available host"
    ])


def is_rate_limit_error(error):
    return getattr(error, "status", 0) == 429 or "too many requests" in str(error).lower()


def main():
    try:
        import oci
    except ImportError:
        log("ERROR: oci SDK not installed. Run: pip install oci")
        return 3

    config = build_oci_config()

    try:
        compute_client = oci.core.ComputeClient(config)
        network_client = oci.core.VirtualNetworkClient(config)
    except Exception as e:
        log(f"ERROR: Failed to initialize OCI clients: {e}")
        return 3

    log("=" * 60)
    log("Oracle A1.Flex One-Shot Creator")
    log(f"Shape: {SHAPE} ({OCPUS} OCPU, {MEMORY_IN_GBS} GB)")
    log(f"Region: {OCI_REGION}")
    log(f"AD: {AVAILABILITY_DOMAIN}")
    log("=" * 60)

    try:
        instance = create_instance(compute_client, network_client)
        public_ip = wait_for_running(compute_client, instance.id)

        msg = f"🎉 Oracle A1.Flex instance CREATED!\n"
        msg += f"Instance ID: {instance.id}\n"
        msg += f"Name: {instance.display_name}\n"
        msg += f"AD: {instance.availability_domain}\n"
        if public_ip:
            msg += f"Public IP: {public_ip}\n"
            msg += f"SSH: ssh -i ~/.ssh/id_rsa ubuntu@{public_ip}"
        else:
            msg += "Public IP: Check Oracle Console"

        notify(msg)
        return 0

    except oci.exceptions.ServiceError as e:
        if is_rate_limit_error(e):
            log(f"Rate limited (429). Will retry on next scheduled run.")
            return 2
        elif is_capacity_error(e):
            log(f"Out of capacity ({e.status}). Will retry on next scheduled run.")
            return 1
        else:
            log(f"ServiceError {e.status}: {e.message}")
            if e.status in (401, 400):
                log("ERROR: Authentication/config issue. Check your secrets.")
                return 3
            return 4

    except Exception as e:
        log(f"Unexpected error: {e}")
        traceback.print_exc()
        return 4


if __name__ == "__main__":
    sys.exit(main())
