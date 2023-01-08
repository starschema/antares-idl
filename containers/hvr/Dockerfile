FROM rockylinux:8

RUN yum -y install libpq perl procps

ENV HVR_HOME /hvr/hvr_home
ENV HVR_CONFIG /hvr/hvr_config
ENV PATH "$PATH:$HVR_HOME/bin"

RUN mkdir -p $HVR_HOME    

WORKDIR ${HVR_HOME}

COPY hvr*tar.gz .
RUN tar xvzf hvr*tar.gz

COPY hvr_docker_init.sh .

ENTRYPOINT [ "./hvr_docker_init.sh" ]