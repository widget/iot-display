<?php

$DATA_LOC = "server.xml";
$ROOT_NODE = "display";
$CLIENT_NODE = "client";
$MAX_ENTRIES = 100;

if (array_key_exists("battery", $_POST) &&
    array_key_exists("reset", $_POST) &&
    array_key_exists("screen", $_POST))
{
    $doc = new DOMDocument('1.0', 'UTF8');

    $doc->formatOutput = true;
    $doc->preserveWhiteSpace = false;

    $now = date("c"); // ISO-8601

    $contents = file_get_contents($DATA_LOC);

    if (!$doc->loadXML($contents))
    {
        // Couldn't load old file, create new one
        $root = $doc->createElement($ROOT_NODE);
        $doc->appendChild($root);
        $client = $doc->createElement($CLIENT_NODE);
        $root->appendChild($client);
    }
    else
    {
        $client = $doc->getElementsByTagName($CLIENT_NODE)->item(0);
    }
    $log_entries = $doc->getElementsByTagName("log");

    if ($log_entries->length >= $MAX_ENTRIES)
    {
        $client->removeChild($log_entries->item(0));
    }

    $new_entry = $doc->createElement("log");
    $client->appendChild($new_entry);
    $new_entry->setAttribute("time", $now);
    $new_entry->setAttribute("ip", $_SERVER["REMOTE_ADDR"]);

    $new_entry->setAttribute("battery", $_POST["battery"]);
    $new_entry->setAttribute("reset", $_POST["reset"]);
    $new_entry->setAttribute("screen", $_POST["screen"]);

    $doc->save($DATA_LOC);
}
else
{
    http_response_code(400);
}
?>
