FROM ubuntu:latest

RUN apt update

# install ssh
RUN apt-get update \
    && apt-get install -y openssh-server iputils-ping telnet iproute2 sudo git

# Expose SSH port
EXPOSE 22

# create user
RUN adduser --home /home/lechatp lechatp
RUN echo "lechatp:lechatp" | chpasswd

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
RUN echo "lechatp ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers


# expose http port
EXPOSE 80

# start ssh service
CMD ["/usr/sbin/sshd", "-D"]