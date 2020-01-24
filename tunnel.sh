#!/bin/sh
ssh -p 438 fonpit@136.243.81.161 -i ~/.ssh/id_ecdsa -L 33066:127.0.0.1:3306 -N
