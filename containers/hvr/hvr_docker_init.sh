#!/bin/sh -x

# TODO: find out why
rm -f /hvr/hvr_home/lib/libcrypt*

hvrhubserverconfig \
    HTTP_Port=${HVR_HTTP_PORT} \
    Repository_Class=${HVR_REPO_CLASS} \
    Database_Host=${HVR_DB_HOST} \
    Database_Port=${HVR_DB_PORT} \
    Database_Name=${HVR_DB_NAME} \
    Database_User=${HVR_DB_USERNAME} \
    Database_Password="${HVR_DB_PASSWORD}" \
    $HVR_SERVER_CONFIG_OPTS

hvrreposconfig -c

hvrlicense ${HVR_HOME}/license/hvr.lic

#hvruserconfig -c admin
#cat /tmp/aa | hvruserconfig -c admin
#hvrreposconfig -A user:admin=SysAdmin

hvrwalletconfig -c Type=DISABLED

hvrhubconfig -c antares Description="Antares HVR Hub"

hvrhubserver -i