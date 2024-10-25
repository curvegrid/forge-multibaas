import sys
import json
import urllib.request
import os
import re
import traceback
import subprocess
from typing import Optional, Dict, Any, Tuple


# Custom Exception for MultiBaas API errors
class MultiBaasAPIError(Exception):
    """
    Exception raised for errors in the MultiBaas API interactions.
    """

    def __init__(self, path: str, status_code: Any, message: str):
        self.path = path
        self.status_code = status_code
        self.message = message
        super().__init__(
            f"MultiBaas API Error [{status_code}] while calling {path}: {message}"
        )


def filter_empty_values(options: Dict[str, str]) -> Dict[str, str]:
    """
    Filters out key-value pairs from a dictionary where the value is an empty string.

    Args:
        options (dict): The dictionary to filter.

    Returns:
        dict: A new dictionary with empty string values removed.
    """
    return {k: v for k, v in options.items() if v}


def mb_request(
    mb_url: str,
    mb_api_key: str,
    path: str,
    method: str = "GET",
    data: Optional[Dict] = None,
) -> Any:
    """
    Helper function for making requests to MultiBaas API.

    Args:
        mb_url (str): The base URL for MultiBaas.
        mb_api_key (str): The API key for authentication.
        path (str): The API endpoint path.
        method (str): HTTP method ('GET', 'POST', 'DELETE').
        data (dict, optional): Data to send in the request body.

    Returns:
        Any: The result from the API call.

    Raises:
        MultiBaasAPIError: If the API call fails.
    """
    url = f"{mb_url}/api/v0/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {mb_api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, method=method)
    for key, value in headers.items():
        req.add_header(key, value)

    if data is not None:
        json_data = json.dumps(data).encode("utf-8")
        req.data = json_data

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)

            # Check for 404 status code and raise a specific error
            if response.status == 404:
                raise MultiBaasAPIError(path, 404, "Not found")

            # Check if the response has "message": "success"
            if res_json.get("message") != "success":
                raise MultiBaasAPIError(
                    path, response.status, res_json.get("message", "Unknown error")
                )

            # Unwrap and return the result
            return res_json.get("result")

    except urllib.error.HTTPError as e:
        raise MultiBaasAPIError(path, e.code, e.reason)
    except urllib.error.URLError as e:
        raise MultiBaasAPIError(path, "URL Error", e.reason)


def get_artifact_dir() -> Optional[str]:
    """
    Retrieve the artifact directory from Forge config.

    Returns:
        Optional[str]: The artifact directory path or None if not found.
    """
    try:
        output = subprocess.run(
            ["forge", "config", "--json"], capture_output=True, text=True
        )
        config = json.loads(output.stdout)
        return config.get("out", "out")  # Fallback to 'out' if not found
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error retrieving artifact directory: {str(e)}")
        return None


def get_multibaas_credentials() -> Tuple[str, str]:
    """
    Validate and retrieve MultiBaas credentials from environment variables.

    Returns:
        (str, str): A tuple containing the MultiBaas URL and API key.

    Exits:
        Exits the program if the environment variables are not set.
    """
    mb_url = os.getenv("MULTIBAAS_URL", "").rstrip("/")  # Strip trailing slashes
    mb_api_key = os.getenv("MULTIBAAS_API_KEY", "")

    if not mb_url or not mb_api_key:
        print(
            "Error: MULTIBAAS_URL and/or MULTIBAAS_API_KEY environment variables are not set."
        )
        sys.exit(1)

    return mb_url, mb_api_key


def validate_api_key(mb_url: str, mb_api_key: str) -> bool:
    """
    Validates the API key by making a request to MultiBaas.

    Args:
        mb_url (str): The MultiBaas URL.
        mb_api_key (str): The API key for authentication.

    Returns:
        bool: True if validation is successful, False otherwise.
    """
    try:
        # Make the request to validate the API key
        result = mb_request(mb_url, mb_api_key, "currentuser")

        if result:
            print("API key validation successful.")
            return True
        else:
            print("API key validation failed.")
            return False
    except MultiBaasAPIError as e:
        print(f"Error during validation: {e}")
        return False


def create_address(
    mb_url: str, mb_api_key: str, address: str, contract_label: str, address_label: str
) -> Optional[Dict]:
    """
    Creates an address in MultiBaas, handling label conflicts and updates.

    Args:
        mb_url (str): The MultiBaas URL.
        mb_api_key (str): The API key for authentication.
        address (str): The Ethereum address to create.
        contract_label (str): The label for the contract.
        address_label (str): The label for the address.

    Returns:
        Optional[Dict]: The created address information or None if failed.
    """
    # Fetch allow_update_address from environment, default to False
    allow_update_address = os.getenv(
        "MULTIBAAS_ALLOW_UPDATE_ADDRESS", "false"
    ).lower() in ["true", "1"]

    try:
        # Check if the address already exists
        result = mb_request(mb_url, mb_api_key, f"/chains/ethereum/addresses/{address}")

        # If the address exists, handle any conflicting labels
        if result and result.get("label", "") != "":
            existing_label = result["label"]

            if existing_label != address_label:
                raise MultiBaasAPIError(
                    f"/chains/ethereum/addresses/{address}",
                    409,
                    f"The address {address} has already been created under a different label '{existing_label}'",
                )

            print(f"Address {address} already created as '{existing_label}'")
            return result

    except MultiBaasAPIError as e:
        if e.status_code != 404:
            raise  # Re-raise exception if it's not a 404 Not Found error
        # If the address is not found (404), proceed to create the address

    # Generate a unique address label if the default is conflicting
    if address_label == contract_label:
        # Check for similar labels and generate a new one if necessary
        similar_labels = mb_request(
            mb_url,
            mb_api_key,
            f"/chains/ethereum/addresses/similarlabels/{contract_label}",
        )
        similar_set = set(label_info["label"] for label_info in similar_labels)
        if contract_label in similar_set:
            # Add a numeric suffix to create a unique label
            num = 2
            while f"{contract_label}{num}" in similar_set:
                num += 1
            address_label = f"{contract_label}{num}"
    else:
        try:
            # Check if the label already exists
            result = mb_request(
                mb_url, mb_api_key, f"/chains/ethereum/addresses/{address_label}"
            )

            if not allow_update_address:
                raise MultiBaasAPIError(
                    f"/chains/ethereum/addresses/{address_label}",
                    409,
                    f"Another address has already been created under the label '{address_label}'",
                )

            # If allow_update_address is True, delete the conflicting address
            if result and result.get("address", "") != "":
                old_address = result["address"]
                print(
                    f"Deleting old address {old_address} with label '{address_label}'"
                )
                mb_request(
                    mb_url,
                    mb_api_key,
                    f"/chains/ethereum/addresses/{address_label}",
                    method="DELETE",
                )

        except MultiBaasAPIError as e:
            if e.status_code != 404:
                raise  # Re-raise exception if it's not a 404 Not Found error
            # If the label is not found (404), proceed to create the address

    # Create the new address
    print(f"Creating address {address} with label '{address_label}'")
    data = {
        "address": address,
        "label": address_label,
    }
    try:
        created_address = mb_request(
            mb_url, mb_api_key, "/chains/ethereum/addresses", method="POST", data=data
        )
        return created_address

    except MultiBaasAPIError as e:
        print(f"Failed to create address: {e}")
        return None


def create_contract(
    mb_url: str,
    mb_api_key: str,
    artifact_dir: str,
    contract_name: str,
    contract_label: str,
    contract_version: Optional[str],
) -> Optional[Dict]:
    """
    Creates or updates a contract in MultiBaas, handling versioning and conflicts.

    Args:
        mb_url (str): The MultiBaas URL.
        mb_api_key (str): The API key for authentication.
        artifact_dir (str): The directory where artifacts are stored.
        contract_name (str): The name of the contract.
        contract_label (str): The label for the contract.
        contract_version (str, optional): The version label for the contract.

    Returns:
        Optional[Dict]: The created or existing contract information or None if failed.
    """
    try:
        # Load the artifact
        artifact_path = os.path.join(
            artifact_dir, f"{contract_name}.sol", f"{contract_name}.json"
        )
        with open(artifact_path, "r") as artifact_file:
            artifact_data = json.load(artifact_file)

        # Extract ABI, bytecode, devdoc, and userdoc
        abi = json.dumps(artifact_data["abi"])
        bytecode = artifact_data["bytecode"]
        if isinstance(bytecode, dict) and "object" in bytecode:
            bytecode = bytecode["object"]

        devdoc = json.dumps(
            artifact_data.get("metadata", {}).get("output", {}).get("devdoc", "{}")
        )
        userdoc = json.dumps(
            artifact_data.get("metadata", {}).get("output", {}).get("userdoc", "{}")
        )

        # Prepare payload with basic contract information
        payload = {
            "label": contract_label,
            "language": "solidity",
            "bin": bytecode,
            "rawAbi": abi,
            "contractName": contract_name,
            "developerDoc": devdoc,
            "userdoc": userdoc,
        }

        # Check if the exact contract version exists
        if contract_version is not None:
            try:
                mb_contract = mb_request(
                    mb_url,
                    mb_api_key,
                    f"/contracts/{contract_label}/{contract_version}",
                )

                # If contracts share the same bytecode, skip creation
                if mb_contract["bin"] == payload["bin"]:
                    print(
                        f"Contract '{mb_contract['contractName']} {mb_contract['version']}' already exists. Skipping creation."
                    )
                    return mb_contract

                # If the bytecode differs, check if updates are allowed
                allow_update_contract = os.getenv(
                    "MULTIBAAS_ALLOW_UPDATE_CONTRACT", "false"
                ).lower() in ["true", "1"]
                if not allow_update_contract:
                    raise MultiBaasAPIError(
                        f"/contracts/{contract_label}/{contract_version}",
                        409,
                        f"A different '{mb_contract['contractName']} {mb_contract['version']}' has already been deployed.",
                    )

                # Delete the old contract if updates are allowed
                print(
                    f"Deleting old contract with label='{contract_label}' and version='{contract_version}' to deploy a new one."
                )
                mb_request(
                    mb_url,
                    mb_api_key,
                    f"/contracts/{contract_label}/{contract_version}",
                    method="DELETE",
                )
            except MultiBaasAPIError as e:
                if e.status_code != 404:
                    raise  # Re-raise exception if it's not a 404 Not Found error
                # If the contract version is not found (404), proceed to create the contract

        # If the version is not provided or needs to be incremented
        if contract_version is None:
            try:
                mb_contract = mb_request(
                    mb_url, mb_api_key, f"/contracts/{contract_label}"
                )

                # Check if contracts share the same bytecode
                if mb_contract["bin"] == payload["bin"]:
                    print(
                        f"Contract '{mb_contract['contractName']} {mb_contract['version']}' already exists. Skipping creation."
                    )
                    return mb_contract

                version = mb_contract["version"]
                # Increment version number if found
                if re.search(r"\d+$", version):
                    version = re.sub(
                        r"\d+$", lambda m: str(int(m.group()) + 1), version
                    )
                else:
                    version += "2"

                contract_version = version
            except MultiBaasAPIError as e:
                if e.status_code != 404:
                    raise  # Re-raise exception if it's not a 404 Not Found error
                contract_version = "1.0"

        # Now that contract_version is finalized, add it to the payload
        payload["version"] = contract_version

        # Proceed to create the contract
        print(f"Creating contract '{contract_label} {contract_version}'")
        mb_contract = mb_request(
            mb_url,
            mb_api_key,
            f"/contracts/{contract_label}",
            method="POST",
            data=payload,
        )

        return mb_contract

    except FileNotFoundError:
        print(f"Error: Artifact JSON file not found at {artifact_path}")
        return None
    except MultiBaasAPIError as e:
        print(f"Failed to create contract: {e}")
        return None


def link_contract_to_address(
    mb_url: str,
    mb_api_key: str,
    contract_label: str,
    contract_version: Optional[str],
    address_label: str,
    starting_block: str,
) -> None:
    """
    Links a contract to an address in MultiBaas.

    Args:
        mb_url (str): The MultiBaas URL.
        mb_api_key (str): The API key for authentication.
        contract_label (str): The label of the contract.
        contract_version (str, optional): The version of the contract.
        address_label (str): The label of the address.
        starting_block (str): The starting block for event syncing.
    """
    data = {
        "label": contract_label,
        "version": contract_version,
        "startingBlock": starting_block,
    }
    try:
        mb_request(
            mb_url,
            mb_api_key,
            f"/chains/ethereum/addresses/{address_label}/contracts",
            method="POST",
            data=data,
        )
    except MultiBaasAPIError as e:
        print(f"Failed to link contract to address: {e}")
        raise


def upload_and_link_contract(
    mb_url: str,
    mb_api_key: str,
    artifact_dir: str,
    contract_name: str,
    contract_address: str,
    options: Dict[str, str],
) -> None:
    """
    Uploads a contract to MultiBaas and links it to an address.

    Args:
        mb_url (str): The MultiBaas URL.
        mb_api_key (str): The API key for authentication.
        artifact_dir (str): The directory where artifacts are stored.
        contract_name (str): The name of the contract.
        contract_address (str): The Ethereum address of the contract.
        options (dict): Additional options for contract and address labeling.
    """
    contract_label = options.get("contractLabel", contract_name.lower())
    contract_version = options.get("contractVersion", None)
    address_label = options.get("addressLabel", contract_label)
    starting_block = options.get("startingBlock", "-100")

    # Create the contract
    mb_contract = create_contract(
        mb_url,
        mb_api_key,
        artifact_dir,
        contract_name,
        contract_label,
        contract_version,
    )
    if not mb_contract:
        print("Error: Failed to create contract. Stopping execution.")
        return

    # Create the address
    mb_address = create_address(
        mb_url, mb_api_key, contract_address, contract_label, address_label
    )
    if not mb_address:
        print("Error: Failed to create address. Stopping execution.")
        return

    # Link the contract to the address
    try:
        link_contract_to_address(
            mb_url,
            mb_api_key,
            contract_label,
            mb_contract.get("version"),
            address_label,
            starting_block,
        )
        print("Contract linked successfully.")
    except MultiBaasAPIError as e:
        print(f"Error: Failed to link contract to address: {e}")


def main() -> None:
    """
    Main function to handle commands and orchestrate the MultiBaas interactions.
    """
    try:
        # Step 1: Retrieve MultiBaas credentials from environment variables
        mb_url, mb_api_key = get_multibaas_credentials()

        # Step 2: Validate the API key
        if not validate_api_key(mb_url, mb_api_key):
            return

        # Step 3: Retrieve the artifact directory from forge config
        artifact_dir = get_artifact_dir()
        if not artifact_dir:
            print("Error: Unable to retrieve the artifact directory.")
            return

        # Step 4: Parse command and arguments
        if len(sys.argv) < 4:
            print(
                "Usage: python3 main.py COMMAND CONTRACT_NAME CONTRACT_ADDRESS OPTIONS"
            )
            return

        command = sys.argv[1]
        contract_name = sys.argv[2]
        contract_address = sys.argv[3]
        options_str = sys.argv[4]

        # Parse options as a dict directly
        options = filter_empty_values(json.loads(options_str))

        # Step 5: Handle the command
        if command == "linkContract":
            upload_and_link_contract(
                mb_url,
                mb_api_key,
                artifact_dir,
                contract_name,
                contract_address,
                options,
            )
        else:
            print(f"Unknown command: {command}")

    except MultiBaasAPIError as e:
        print(f"MultiBaas API error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
