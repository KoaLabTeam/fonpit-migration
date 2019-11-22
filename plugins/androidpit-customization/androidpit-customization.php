<?php
/**
 * Plugin Name: AndroidPit Customizations 
 * Description: This adds custom post types like review, news, poll, opinion and so forth
 * Author: Mario Scheliga
 * Author URI: https://github.com/marsch
 * Version: 0.1
 */


/**
 * Align hashing of password to apit once
 */
if ( !function_exists('wp_hash_password') ){
  function wp_hash_password($password) {
    //apply your own hashing structure here
    return  base64_encode(sha1($password, true));
  }
}

if ( !function_exists('wp_check_password') ){
  function wp_check_password($password, $hash, $user_id = '') {
    //check for your hash match
    $hashed_passwd = base64_encode(sha1($password, true));
    $check = $hashed_passwd === $hash;
    return apply_filters('check_password', $check, $password, $hash, $user_id);
  }
}
?>