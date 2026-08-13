#!/usr/bin/env php
<?php
/**
 * Initialize a Phabricator admin user with fixed credentials for integration testing.
 *
 * Run this after `bin/storage upgrade --force` inside the phabricator container.
 * The compose.yml post_start hook calls this automatically.
 *
 * Credentials created:
 *   Username:       admin
 *   Email:          admin@localhost
 *   Login Password: test
 *   API Token:      cli-aaaaaaaaaaaaaaaaaaaaaaaaaaaa
 *   VCS Password:   test
 */

require_once '/opt/phabricator/scripts/init/init-script.php';

PhabricatorEnv::initializeWebEnvironment();

$username    = 'admin';
$email       = 'admin@localhost';
$realname    = 'Admin User';
$login_pass  = 'test';
$api_token   = 'cli-aaaaaaaaaaaaaaaaaaaaaaaaaaaa';
$vcs_pass    = 'test';

$actor = PhabricatorUser::getOmnipotentUser();

// ---- Enable username/password authentication ----
// Required before a login password can be used. Skipped if already configured.
echo "Configuring password authentication provider...\n";
$auth_config = id(new PhabricatorAuthProviderConfig())
    ->loadOneWhere('providerClass = %s', 'PhabricatorPasswordAuthProvider');
if (!$auth_config) {
    id(new PhabricatorAuthProviderConfig())
        ->setProviderClass('PhabricatorPasswordAuthProvider')
        ->setProviderType('password')
        ->setProviderDomain('self')
        ->setIsEnabled(1)
        ->setShouldAllowLogin(1)
        ->setShouldAllowRegistration(0)
        ->setShouldAllowLink(1)
        ->setShouldAllowUnlink(0)
        ->save();
    echo "Password authentication provider enabled.\n";
} else {
    echo "Password authentication provider already configured.\n";
}

// ---- Create or find admin user ----
$user = id(new PhabricatorUser())->loadOneWhere('userName = %s', $username);
if ($user) {
    echo "Admin user already exists (PHID: {$user->getPHID()})\n";
} else {
    echo "Creating admin user...\n";
    $user = id(new PhabricatorUser())
        ->setUsername($username)
        ->setRealName($realname)
        ->setIsAdmin(1)
        ->setIsApproved(1);
    $email_obj = id(new PhabricatorUserEmail())
        ->setAddress($email)
        ->setIsVerified(1);
    id(new PhabricatorUserEditor())
        ->setActor($actor)
        ->createNewUser($user, $email_obj);
    echo "Admin user created (PHID: {$user->getPHID()})\n";
}

// The default account state is pending approval, which prohibits login and
// Conduit access even for an administrator.
$user
    ->setIsApproved(1)
    ->setIsDisabled(0)
    ->save();

// ---- Set login password ----
echo "Setting login password...\n";
$password = id(new PhabricatorAuthPassword())
    ->loadOneWhere(
        'objectPHID = %s AND passwordType = %s',
        $user->getPHID(),
        PhabricatorAuthPassword::PASSWORD_TYPE_ACCOUNT);
if (!$password) {
    $password = PhabricatorAuthPassword::initializeNewPassword(
        $user,
        PhabricatorAuthPassword::PASSWORD_TYPE_ACCOUNT);
}
$password
    ->setPassword(new PhutilOpaqueEnvelope($login_pass), $user)
    ->save();
echo "Login password set.\n";

// ---- Set Conduit API token ----
// Delete any existing tokens and install a single fixed one so the value is
// predictable across container restarts.
echo "Setting API token...\n";
$existing_tokens = id(new PhabricatorConduitToken())
    ->loadAllWhere('objectPHID = %s', $user->getPHID());
foreach ($existing_tokens as $t) {
    $t->delete();
}
id(new PhabricatorConduitToken())
    ->setObjectPHID($user->getPHID())
    ->setTokenType(PhabricatorConduitToken::TYPE_STANDARD)
    ->setToken($api_token)
    ->setExpires(null)
    ->save();
echo "API token set: {$api_token}\n";

// ---- Set VCS HTTP password ----
echo "Setting VCS HTTP password...\n";
$vcs = id(new PhabricatorAuthPassword())
    ->loadOneWhere(
        'objectPHID = %s AND passwordType = %s',
        $user->getPHID(),
        PhabricatorAuthPassword::PASSWORD_TYPE_VCS);
if (!$vcs) {
    $vcs = PhabricatorAuthPassword::initializeNewPassword(
        $user,
        PhabricatorAuthPassword::PASSWORD_TYPE_VCS);
}
$vcs
    ->setPassword(new PhutilOpaqueEnvelope($vcs_pass), $user)
    ->save();
echo "VCS HTTP password set.\n";

echo "\n=== Phabricator admin user ready ===\n";
echo "  Username:       {$username}\n";
echo "  Email:          {$email}\n";
echo "  Login Password: {$login_pass}\n";
echo "  API Token:      {$api_token}\n";
echo "  VCS Password:   {$vcs_pass}\n";
