// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;

import {Vm} from "forge-std/Vm.sol";
import {console} from "forge-std/console.sol";

library MultiBaas {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    // Encode options for uploading and linking a contract MultiBaas
    // @param contractLabel: Label for the contract. Defaults to contract name if empty
    // @param addressLabel: Label for the contract address. Defaults to contract name if empty
    // @param contractVersion: Version label for the contract. Defaults to 1.0 and auto increments if empty
    // @param startingBlock: From which block to start syncing events. Defaults to -100. If a negative value, it represents blocks before the current block. If a positive value, it represents the absolute block number. If 0, it represents the latest block.
    function withOptions(
        string memory contractLabel,
        string memory addressLabel,
        string memory contractVersion,
        string memory startingBlock
    ) internal pure returns (bytes memory encodedOptions) {
        encodedOptions = abi.encodePacked(
            '{"contractLabel":"',
            contractLabel,
            '","addressLabel":"',
            addressLabel,
            '","contractVersion":"',
            contractVersion,
            '","startingBlock":"',
            startingBlock,
            '"}'
        );
    }

    // Link a contract to MultiBaas with options
    function linkContractWithOptions(string memory contractName, address contractAddress, bytes memory encodedOptions)
        internal
    {
        // Construct the command to call the Python script
        string[] memory inputs = new string[](6);
        string memory scriptPath = string.concat(vm.projectRoot(), "/lib/forge-multibaas/main.py");
        inputs[0] = "python3";
        inputs[1] = scriptPath;
        inputs[2] = "linkContract";
        inputs[3] = contractName;
        inputs[4] = toString(contractAddress);
        inputs[5] = string(encodedOptions);

        // Call the Python script using ffi
        bytes memory res = vm.ffi(inputs);

        // Log the response from MultiBaas
        console.log("Link Contract: %s", string(res));
    }

    // Link a contract to MultiBaas with default options
    function linkContract(string memory contractName, address contractAddress) internal {
        bytes memory defaultEncodedOptions = withOptions("", "", "", "");
        return linkContractWithOptions(contractName, contractAddress, defaultEncodedOptions);
    }

    // Utility function to convert an address to a string for Python
    function toString(address _address) internal pure returns (string memory) {
        bytes32 value = bytes32(uint256(uint160(_address)));
        bytes memory alphabet = "0123456789abcdef";

        bytes memory str = new bytes(42);
        str[0] = "0";
        str[1] = "x";
        for (uint256 i = 0; i < 20; i++) {
            str[2 + i * 2] = alphabet[uint8(value[i + 12] >> 4)];
            str[3 + i * 2] = alphabet[uint8(value[i + 12] & 0x0f)];
        }
        return string(str);
    }
}
