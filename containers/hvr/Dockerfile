FROM rockylinux:8

ARG UNAME=hvrhub
ARG UID=1001
ARG GID=1001

RUN groupadd -g $GID -o $UNAME
RUN useradd -m -u $UID -g $GID -o -s /bin/bash $UNAME

RUN yum -y install libpq perl procps nc

ENV HVR_HOME /hvr/hvr_home
ENV HVR_CONFIG /hvr/hvr_config
ENV PATH "$PATH:$HVR_HOME/bin"

RUN mkdir -p $HVR_HOME    

WORKDIR ${HVR_HOME}

COPY fivetran*tar.gz .
RUN tar xvzf fivetran*tar.gz
RUN rm -f $HVR_HOME/lib/libcrypt*

COPY hvr_docker_init.sh .


USER $UNAME


ENTRYPOINT [ "./hvr_docker_init.sh" ]