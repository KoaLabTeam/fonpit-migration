<?php
/**
 * Plugin Name: AndroidPit Migration Helper
 * Description: This plugin is used to register some custom fields within the rest api to easier update and import old content items (posts, users, media, etc)
 * Author: Mario Scheliga
 * Author URI: https://github.com/marshc
 * Version: 0.1
 */

add_action( 'rest_api_init', function() {
  $object_type = 'post';
  $article_meta_args = array(
      'type'         => 'string',
      'description'  => 'the article id with in the cms to migrate from',
      'single'       => true,
      'show_in_rest' => true,
  );
  register_post_meta( 'post', 'legacy_article_id', $article_meta_args );

  $media_meta_args = array(
    'type'           => 'string',
    'description'    => 'the user file id with in the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );
  register_post_meta('attachment', 'legacy_userfile_id', $media_meta_args);

  $media_user_meta_args = array(
    'type'           => 'string',
    'description'    => 'the user image id with in the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );
  register_post_meta('attachment', 'legacy_userimage_id', $media_user_meta_args);

  $user_meta_args = array(
    'type'           => 'string',
    'description'    => 'the user id of an user within the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );
  register_meta('user', 'legacy_user_id', $user_meta_args);

  $user_avatar_args = array(
    'type'           => 'integer',
    'description'    => 'the user id of an user within the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );

  register_meta('user', 'wp_user_avatar', $user_avatar_args);

  $comment_legacy_id_args = array(
    'type'           => 'string',
    'description'    => 'the legacy id of a comment within the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );
  register_meta('comment', 'legacy_comment_id', $comment_legacy_id_args);

  $comment_legacy_parentid_args = array(
    'type'           => 'string',
    'description'    => 'the legacy parentid of a comment within the cms to migrate',
    'single'         => true,
    'show_in_rest'   => true,
  );
  register_meta('comment', 'legacy_comment_parentid', $comment_legacy_parentid_args);
  
 });

 ?>