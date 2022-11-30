### secquiry

## Installation of Secquiry and Collablio

# Instructions for Debian 11
```
  apt install git docker.io
  wget https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
  dpkg -i packages-microsoft-prod.deb
  apt-get update; \
  apt-get install -y apt-transport-https && \
  apt-get update && \
  apt-get install -y dotnet-sdk-3.1


  mkdir /src
  cd /src
  git clone https://github.com/0x0abc123/collablio.git
  git clone https://github.com/0x0abc123/secquiry-asoc.git
  cd /src/collablio
  dotnet add package Microsoft.AspNetCore.Owin -v 3.1
  dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer -v 3.1
  dotnet add package Dgraph
  ./build.sh
  cd dgraph
  ./setup.sh
  ./adduser.sh
  cd ..
  dotnet run
```
# connect via ssh tunnel
  ssh -L 5000:127.0.0.1:5000 root@<ipOfServer>

visit 
  http://127.0.0.1:5000/index.html

test it with this:
curl "http://127.0.0.1:5000/nodes" -H 'Content-Type: application/json' -d '{"uids":["0x2","0x3"],"depth":1}'
and should see a response like:
{"timestamp":0,"error":false}
