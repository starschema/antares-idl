FROM rockylinux:8

ENV HVR_HOME /hvr/hvr_home
ENV HVR_CONFIG /hvr/hvr_config
ENV HVR_TMP /hvr/tmp
ENV PATH "$PATH:$HVR_HOME/bin"

RUN mkdir -p $HVR_HOME    

WORKDIR ${HVR_HOME}

COPY hvr*tar.gz .
RUN tar xvzf hvr*tar.gz