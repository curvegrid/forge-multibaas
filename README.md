# Forge MultiBaas Library

The `forge-multibaas` library allows developers to easily upload and link their Solidity contracts to a [MultiBaas](https://www.curvegrid.com/multibaas/) deployment as they develop and deploy smart contracts using [Foundry Forge](https://book.getfoundry.sh/).

Forge is a high-performance, portable, and modular Ethereum development toolchain that enables developers to compile, test, deploy, and interact with Solidity smart contracts. It is a part of the broader Foundry project, which aims to provide an easy-to-use and fast toolkit for blockchain development on Ethereum-compatible networks.

By integrating the `forge-multibaas` library, you can streamline your development workflow by automatically uploading and linking your contracts to a MultiBaas deployment directly from your Forge scripts.

For more information on how to use MultiBaas, please see our [docs](https://docs.curvegrid.com/multibaas/).

## Installation

If you have not already setup Forge, follow the [Foundry installation guide](https://book.getfoundry.sh/getting-started/installation.html).

Then, install the library into your project by running:

```bash
forge install curvegrid/forge-multibaas
```

## System Requirements

The Forge MultiBaas library relies on Python 3 to run its backend operations. Ensure that Python 3 is installed and can be run in your terminal via the `python3` command.

### Foundry Setup Requirements

Make sure your `foundry.toml` file includes the following:

```toml
libs = ["lib"]
```

This is necessary due to the way the library is added as a submodule to your Foundry project.

## Environment Setup

The library requires certain environment variables to be defined:

- `MULTIBAAS_URL`: The MultiBaas deployment URL, including the protocol (e.g., `https://`)
- `MULTIBAAS_API_KEY`: An API key created on the MultiBaas deployment with admin group permissions.

Optionally, the following variables can be set to bypass safeguards:

- `MULTIBAAS_ALLOW_UPDATE_CONTRACT=true`: Allows contracts to be reuploaded and labelled as an already existing version in MultiBaas, even if the bytecode changes.
- `MULTIBAAS_ALLOW_UPDATE_ADDRESS=true`: Allows addresses to be updated in MultiBaas if the address label conflicts.

If you choose to set these variables using an `.env` file, since the `MULTIBAAS_API_KEY` grants full admin access to the MultiBaas deployment, we strongly advise against checking it into source control.

## Usage

### Deploying Contracts with MultiBaas

The library provides a simple interface for linking contracts to MultiBaas. Building on top of the [`hello_foundry` tutorial](https://book.getfoundry.sh/projects/creating-a-new-project), here’s an example Counter deployment script (`script/Counter.s.sol`) that uses the library.

Please note that in order for this example deployment script to run, the `PRIVATE_KEY` environment variable should be set to your `0x`-prefixed deployer private key.

```solidity
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {Script} from "forge-std/Script.sol";
import {MultiBaas} from "forge-multibaas/MultiBaas.sol";
import {Counter} from "../src/Counter.sol";

contract CounterScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        // Deploy the first NFT contract
        Counter counter = new Counter();

        // Upload and link the contract in MultiBaas with default options
        MultiBaas.linkContract("Counter", address(counter));

        // Deploy a second Counter contract
        Counter secondCounter = new Counter();

        // Upload and link the second contract in MultiBaas with custom options
        bytes memory encodedOptions = MultiBaas.withOptions(
            "counter", // Arbitrary MultiBaas label for the uploaded contract code and associated ABI
            "counter", // Arbitrary MultiBaas label for the address at which the contract is deployed
            "1.5", // Arbitrary MultiBaas version label for the uploaded contract code and associated ABI
            "-50" // Start syncing events from 50 blocks prior to the current network block
        );
        MultiBaas.linkContractWithOptions("Counter", address(secondCounter), encodedOptions);

        vm.stopBroadcast();
    }
}
```

For details on the encoded options, please see the section on [Options Encoding](#options-encoding).

### Running the Script

To run the deployment script and broadcast the transactions, use the following command. Please note that this command requires the `NETWORK_RPC_URL` environment variable to have been set to an HTTP or WS RPC endpoint of the same network that the MultiBaas deployment is connected to.

```bash
forge script script/Counter.s.sol:CounterScript --rpc-url $NETWORK_RPC_URL --broadcast --ffi
```

**Note:** The script must be run with the [`--ffi` flag](https://book.getfoundry.sh/cheatcodes/ffi) to allow the Python script for MultiBaas integration to be executed. Alternatively, the `ffi = true` flag can be set in the `foundry.toml` file. Note that FFI allows for arbitrary code to be executed by any Forge library, and for now it is a workaround as configuring MultiBaas requires making HTTP calls which are not yet natively supported in Forge.

### Forge MultiBaas Library Functions

The `forge-multibaas` library provides the following key functions:

- `linkContract`: Links a contract to MultiBaas with default options.
- `linkContractWithOptions`: Allows you to link a contract to MultiBaas with custom options, such as custom labels, versioning, and event syncing blocks.

#### Example Usage in Solidity:

```solidity
bytes memory encodedOptions = MultiBaas.withOptions(
    "custom_contract_label", // Arbitrary MultiBaas label for the uploaded contract code and associated ABI
    "custom_address_label", // Arbitrary MultiBaas label for the address at which the contract is deployed
    "1.0", // Arbitrary MultiBaas version label for the uploaded contract code and associated ABI
    "-100" // Start syncing events from 100 blocks prior to the current network block
);
MultiBaas.linkContractWithOptions("MyContract", address(myContract), encodedOptions);
```

### Options Encoding

You can customize the following options when linking contracts:

- **`contractLabel`**: The label for the contract. Defaults to the contract name in lowercase.
- **`addressLabel`**: The label for the contract address. Defaults to the contract name in lowercase.
- **`contractVersion`**: The version label for the contract. Defaults to `1.0` and if left empty it auto-increments as the contract bytecode changes. If it is set to a version string that is already uploaded to MultiBaas, but the contract bytecode has changed, then the `MULTIBAAS_ALLOW_UPDATE_CONTRACT` environment variable must be set to `true` to allow for the version label to be reused on the new contract bytecode.
- **`startingBlock`**: The block number from which to start syncing events in MultiBaas. Negative values represent blocks before the current block; non-negative values represent absolute block numbers on the blockchain. `"latest"` represents the current block. If unspecified, it defaults to `"-100"`.
