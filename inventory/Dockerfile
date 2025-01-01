FROM ubuntu:latest

RUN apt update

# install ssh
RUN apt-get update \
    && apt-get install -y openssh-server iputils-ping telnet iproute2 sudo git clang curl

# Expose SSH port
EXPOSE 22

# create user
RUN adduser --home /home/lechatp lechatp
RUN echo "lechatp:lechatp" | chpasswd

# create ansible group
RUN groupadd ansible
RUN usermod -aG ansible lechatp

# create ssh directory
RUN mkdir /home/lechatp/.ssh
RUN mkdir -pm0755 /run/sshd

# copy ssh public key
COPY ansible_rsa.pub /home/lechatp/.ssh/authorized_keys

# set permissions
RUN chown -R lechatp:lechatp /home/lechatp/.ssh
RUN chmod 700 /home/lechatp/.ssh
RUN chmod 600 /home/lechatp/.ssh/authorized_keys

# allow ssh user to sudo
RUN echo "%ansible ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER lechatp

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

RUN . "$HOME/.cargo/env"

USER root

# start ssh service
CMD ["/usr/sbin/sshd", "-D"]