<?php

$DATA_LOC = "log.xml";
$ROOT_NODE = "display";
$CLIENT_NODE = "client";
$MAX_ENTRIES = 100;

$doc = new DOMDocument();

$doc->formatOutput = true;
$doc->preserveWhiteSpace = false;

$now = date("c"); // ISO-8601

if (!$doc->load($DATA_LOC))
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
    $doc->removeChild($log_entries->item(0));
}

$new_entry = $doc->createElement("log");
$client->appendChild($new_entry);
$new_entry->setAttribute("time", $now);
$new_entry->setAttribute("ip", $_SERVER["REMOTE_ADDR"]);

// We'll be moving these checks up, but just to start with

if (array_key_exists("battery", $_POST))
    $new_entry->setAttribute("battery", $_POST["battery"]);

if (array_key_exists("reset", $_POST))
    $new_entry->setAttribute("reset", $_POST["reset"]);

if (array_key_exists("screen", $_POST))
    $new_entry->setAttribute("screen", $_POST["screen"]);

$doc->save($DATA_LOC);

?>
