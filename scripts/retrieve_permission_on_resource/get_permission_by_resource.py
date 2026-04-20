"""
Analisi IAM - Ruoli con accesso a una risorsa specifica.

Output: CSV semicolon-delimited compatibile con la lambda infra-sec-access-validator-alert.
Colonne: ARN;Access;Resources
Access level: Full | ReadOnly | ReadWrite
"""

import boto3
import csv
import sys
from botocore.exceptions import ClientError, ProfileNotFound
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

MAX_WORKERS = 10  # Numero massimo di thread in parallelo

# ---------------------------------------------------------------------------
# Azioni considerate per la classificazione dell'access level
# ---------------------------------------------------------------------------
_READ_ACTIONS = {
    # DynamoDB
    "dynamodb:getitem", "dynamodb:batchgetitem", "dynamodb:query", "dynamodb:scan",
    "dynamodb:describestream", "dynamodb:getrecords", "dynamodb:getstreamrecords",
    # S3
    "s3:getobject", "s3:listbucket", "s3:headobject", "s3:getobjectversion",
    "s3:listbucketversions", "s3:getobjectacl",
}
_WRITE_ACTIONS = {
    # DynamoDB
    "dynamodb:putitem", "dynamodb:updateitem", "dynamodb:batchwriteitem",
    # S3
    "s3:putobject", "s3:copyobject",
}
_FULL_SERVICE_WILDCARDS = {
    "*", "dynamodb:*", "s3:*",
}


def get_iam_client(profile_name=None):
    """Crea client IAM con profilo specificato."""
    try:
        session = boto3.Session(profile_name=profile_name)
        return session.client("iam")
    except ProfileNotFound:
        print(f"❌ Profilo AWS '{profile_name}' non trovato.")
        sys.exit(1)


def get_managed_policy_document(iam, policy_arn):
    """Recupera documento policy gestita."""
    try:
        policy = iam.get_policy(PolicyArn=policy_arn)
        version_id = policy["Policy"]["DefaultVersionId"]
        version = iam.get_policy_version(PolicyArn=policy_arn, VersionId=version_id)
        return version["PolicyVersion"]["Document"]
    except ClientError:
        return {}


def get_inline_policy_document(iam, role_name, policy_name):
    """Recupera documento policy inline."""
    try:
        resp = iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)
        return resp["PolicyDocument"]
    except ClientError:
        return {}


def _service_prefix(resource_arn):
    """
    Estrae il prefisso di servizio dall'ARN della risorsa.
    Es. "arn:aws:dynamodb:..." → "dynamodb"
         "arn:aws:s3:::..."    → "s3"
    """
    parts = resource_arn.split(":")
    if len(parts) >= 3:
        return parts[2].lower()
    return ""


def _action_matches_service(action, service):
    """
    Restituisce True se l'azione appartiene al servizio indicato.
    Es. "dynamodb:getitem" → True per service="dynamodb"
        "*"               → True (wildcard globale)
    """
    action = action.lower()
    if action == "*":
        return True
    prefix = action.split(":")[0]
    return prefix == service


def _collect_actions_for_resource(policy_doc, risorsa):
    """
    Restituisce l'insieme di tutte le azioni Allow che riguardano la risorsa.

    Logica di match sulla risorsa dello statement:
    - Se la risorsa è nell'elenco esatto → match diretto, tutte le azioni.
    - Se la risorsa è "*" → match solo se l'azione appartiene al servizio
      della risorsa target (evita falsi positivi da policy multi-servizio).
    """
    actions = set()
    if not policy_doc:
        return actions

    service = _service_prefix(risorsa)

    statements = policy_doc.get("Statement", [])
    if not isinstance(statements, list):
        statements = [statements]

    for stmt in statements:
        if stmt.get("Effect", "Allow") != "Allow":
            continue

        resources = stmt.get("Resource", [])
        if isinstance(resources, str):
            resources = [resources]

        exact_match    = risorsa in resources
        wildcard_match = "*" in resources

        if not exact_match and not wildcard_match:
            continue

        raw_actions = stmt.get("Action", [])
        if isinstance(raw_actions, str):
            raw_actions = [raw_actions]

        for action in raw_actions:
            # Con Resource "*" accettiamo solo le azioni del servizio corretto
            if wildcard_match and not exact_match:
                if not _action_matches_service(action, service):
                    continue
            actions.add(action.lower())

    return actions


def _classify_access(actions):
    """
    Classifica le azioni in Full | ReadWrite | ReadOnly.
    Restituisce None se non c'è nessun permesso rilevante.
    """
    if not actions:
        return None

    # Se c'è un wildcard → Full
    if actions & _FULL_SERVICE_WILDCARDS:
        return "Full"

    has_read  = bool(actions & _READ_ACTIONS)
    has_write = bool(actions & _WRITE_ACTIONS)

    if has_read and has_write:
        return "ReadWrite"
    if has_read:
        return "ReadOnly"
    if has_write:
        # Write-only: trattiamo come ReadWrite per non perdere i permessi
        return "ReadWrite"

    # Azioni presenti ma non classificabili → Full per sicurezza
    return "Full"


def _extract_role_name(role_arn):
    """
    Estrae il nome del ruolo dall'ARN.
    Es. "arn:aws:iam::123456789:role/MyRole" → "MyRole"
         "arn:aws:iam::123456789:role/path/To/MyRole" → "MyRole"
    """
    if ":role/" in role_arn:
        return role_arn.split(":role/")[-1].split("/")[-1]
    return role_arn


def analizza_ruolo(iam, role, risorsa):
    """
    Analizza un singolo ruolo: restituisce (role_name, role_arn, access_level, risorsa)
    se il ruolo ha accesso alla risorsa, altrimenti None.
    """
    role_name = role["RoleName"]
    role_arn  = role["Arn"]
    all_actions = set()

    try:
        # Policy gestite
        attached = iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
        for ap in attached:
            doc = get_managed_policy_document(iam, ap["PolicyArn"])
            all_actions |= _collect_actions_for_resource(doc, risorsa)

        # Policy inline
        for ip in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
            doc = get_inline_policy_document(iam, role_name, ip)
            all_actions |= _collect_actions_for_resource(doc, risorsa)

    except Exception:
        pass

    access_level = _classify_access(all_actions)
    if access_level is None:
        return None

    return role_name, role_arn, access_level, risorsa


def main():
    print("🔐 Analisi IAM - Ruoli con accesso a una risorsa specifica\n")
    profile  = input("👉 Inserisci il nome del profilo AWS (es. default): ").strip()
    risorsa  = input("👉 Inserisci l'ARN esatto della risorsa (es. arn:aws:dynamodb:...:table/MyTable): ").strip()
    out_file = input("👉 Nome file CSV di output (es. authorized_roles.csv): ").strip() or "authorized_roles.csv"

    iam = get_iam_client(profile)

    print("\n📋 Recupero lista ruoli...")
    roles = []
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        roles.extend(page["Roles"])

    print(f"🔎 Trovati {len(roles)} ruoli, inizio analisi...\n")

    risultati = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(analizza_ruolo, iam, role, risorsa): role for role in roles}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Analisi ruoli", unit="ruolo"):
            result = future.result()
            if result:
                risultati.append(result)

    print("\n✅ Analisi completata.\n")

    if not risultati:
        print(f"❌ Nessun ruolo ha accesso alla risorsa: {risorsa}")
        return

    # Scrivi il CSV nel formato atteso dalla lambda (colonne: Role;ARN;Access;Resources)
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Role", "ARN", "Access", "Resources"])
        for role_name, role_arn, access_level, resource in sorted(risultati, key=lambda r: r[0]):
            writer.writerow([role_name, role_arn, access_level, resource])

    print(f"📄 CSV salvato in: {out_file}  ({len(risultati)} righe)\n")
    print(f"{'Role':<40} {'ARN':<70} {'Access':<12} Resources")
    print("-" * 150)
    for role_name, role_arn, access_level, resource in sorted(risultati, key=lambda r: r[0]):
        print(f"{role_name:<40} {role_arn:<70} {access_level:<12} {resource}")


if __name__ == "__main__":
    main()
