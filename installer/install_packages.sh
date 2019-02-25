#! /bin/bash

function gen_pkgs_to_install() {
    local package=$1
    local pkgs=''
    local pkg_data=$(apt-cache show ${package})
    if [[ $? -ne 0 ]]; then
        logit "Version ${VERSION} not found for ${PACKAGE}"
        exit 2
    fi
    local ps=( $(echo "${pkg_data}" | grep Depends | head -n 1 | sed 's/^Depends:// ; s/([<>]=[^()]\+)/g /; s/([<>]\{1,2\}[^()]\+)//g ; s/[() ]//g; s/,/ /g') )
    local pstr="$package"
    local p
    local dps
    for p in "${ps[@]}"; do
        if [[ $p =~ '=' ]]; then
            pstr="$pstr\n$p"
            dps=$(gen_pkgs_to_install $p)
            logit "package: $p needs: ${dps//$'\n'/,}"
            pstr="$pstr\n$dps"
        fi
    done
    echo -e "$pstr" | sort -u
}

function logit() {
    if [[ $SILENT != true ]]; then
        echo "${1}" >&2
    fi
}

function print_usage() {
    logit 'Description: Install a specified version of a package and its compatible dependencies'
    logit 'Usage: install_packages [-s] [-d] [-n network] [-v version] package'
    logit '                         -s Silent operation - suppresses logging output'
    logit '                         -d Dry run - No installations are actually done'
    logit '                         -n Network to be compatible with.'
    logit '                         -v Version to install. Overrides -n'
}

function yaml() {
   cat <<EOF | /usr/bin/python3
import yaml
yml="""
$1
"""
net='$2'
pkg='$3'
print(yaml.load(yml)[net][pkg])
EOF
}

SILENT=false
DRY_RUN=false
CONF_URL="https://raw.githubusercontent.com/sovrin-foundation/steward-tools/master/installer/network_pkg_versions"

while getopts 'sdf:n:v:' flag; do
case "$flag" in
    s) SILENT=true;;
    d) DRY_RUN=true;;
    n) NETWORK=$OPTARG;;
    v) VERSION=$OPTARG;;
esac
done

PACKAGE=${@:$OPTIND:1}
if [[ $PACKAGE == '' ]]; then
    logit 'Error: a package name must be provided'
    print_usage
    exit 1
fi

if [[ $VERSION == '' ]]; then
    if [[ $NETWORK == '' ]]; then
        logit 'Error: Either a version must be specified, or a network to match versions with must be given'
        print_usage
        exit 1
    else
        logit "${CONF_URL} will be searched for version information for the ${PACKAGE} on ${NETWORK}"
        NETWORK_VERSIONS=`curl -s ${CONF_URL}`
        VERSION=`yaml "${NETWORK_VERSIONS}" "${NETWORK}" "${PACKAGE}"`
    fi
fi

logit "The package to install is ${PACKAGE} version ${VERSION}"

PACKAGES=$(gen_pkgs_to_install ${PACKAGE}=${VERSION} | paste -s -d ' ')
logit ""

if [[ $DRY_RUN == true ]]; then
    logit "Dry run complete. This is the install instruction that would be run otherwise:"
    logit "sudo apt install ${PACKAGES}"
else 
    logit "Installing..."
    logit "sudo apt install ${PACKAGES}"
    if [[ $SILENT == true ]]; then
        sudo apt install -y -q ${PACKAGES}
    else
        sudo apt install ${PACKAGES}
    fi
fi
