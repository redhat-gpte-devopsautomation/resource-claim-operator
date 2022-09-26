#!/usr/bin/env python3
import asyncio
import kopf
import logging

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from config import core_v1_api, custom_objects_api, manage_claims_interval, manage_handles_interval, operator_domain, operator_version
from configure_kopf_logging import configure_kopf_logging
from infinite_relative_backoff import InfiniteRelativeBackoff

from resource_claim import ResourceClaim
from resource_handle import ResourceHandle
from resource_pool import ResourcePool
from resource_provider import ResourceProvider
from resource_watcher import ResourceWatcher


@kopf.on.startup()
async def startup(logger: kopf.ObjectLogger, settings: kopf.OperatorSettings, **_):
    # Store last handled configuration in status
    settings.persistence.diffbase_storage = kopf.StatusDiffBaseStorage(field='status.diffBase')

    # Never give up from network errors
    settings.networking.error_backoffs = InfiniteRelativeBackoff()

    # Use operator domain as finalizer
    settings.persistence.finalizer = operator_domain

    # Store progress in status.
    settings.persistence.progress_storage = kopf.StatusProgressStorage(field='status.kopf.progress')

    # Only create events for warnings and errors
    settings.posting.level = logging.WARNING

    # Disable scanning for CustomResourceDefinitions updates
    settings.scanning.disabled = True

    # Configure logging
    configure_kopf_logging()

    # Preload for matching ResourceClaim templates
    await ResourceProvider.preload(logger=logger)
    await ResourceHandle.preload(logger=logger)


@kopf.on.cleanup()
async def cleanup(logger: kopf.ObjectLogger, **_):
    await ResourceWatcher.stop_all()
    await core_v1_api.api_client.close()
    await custom_objects_api.api_client.close()


@kopf.on.create(operator_domain, operator_version, 'resourceclaims', id='resource_claim_create')
@kopf.on.resume(operator_domain, operator_version, 'resourceclaims', id='resource_claim_resume')
@kopf.on.update(operator_domain, operator_version, 'resourceclaims', id='resource_claim_update')
async def resource_claim_event(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    resource_claim = await ResourceClaim.register(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_claim.manage(logger=logger)


@kopf.on.delete(operator_domain, operator_version, 'resourceclaims')
async def resource_claim_delete(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    resource_claim = ResourceClaim(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_claim.handle_delete(logger=logger)
    await ResourceClaim.unregister(name=name, namespace=namespace)


@kopf.daemon(operator_domain, operator_version, 'resourceclaims',
    cancellation_timeout = 1,
    initial_delay = manage_handles_interval,
)
async def resource_claim_daemon(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    stopped: Optional[datetime],
    uid: str,
    **_
):
    resource_claim = await ResourceClaim.register(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    try:
        while not stopped:
            await resource_claim.manage(logger=logger)
            await asyncio.sleep(manage_claims_interval)
    except asyncio.CancelledError:
        pass


@kopf.on.create(operator_domain, operator_version, 'resourcehandles', id='resource_handle_create')
@kopf.on.resume(operator_domain, operator_version, 'resourcehandles', id='resource_handle_resume')
@kopf.on.update(operator_domain, operator_version, 'resourcehandles', id='resource_handle_update')
async def resource_handle_event(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    resource_handle = await ResourceHandle.register(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_handle.manage(logger=logger)


@kopf.on.delete(operator_domain, operator_version, 'resourcehandles')
async def resource_handle_delete(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    await ResourceHandle.unregister(name, logger=logger)
    resource_handle = ResourceHandle(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_handle.handle_delete(logger=logger)


@kopf.daemon(operator_domain, operator_version, 'resourcehandles',
    cancellation_timeout = 1,
    initial_delay = manage_handles_interval,
)
async def resource_handle_daemon(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    stopped: Optional[datetime],
    uid: str,
    **_
):
    resource_handle = await ResourceHandle.register(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    try:
        while not stopped:
            await resource_handle.manage(logger=logger)
            await asyncio.sleep(manage_handles_interval)
    except asyncio.CancelledError:
        pass


@kopf.on.create(operator_domain, operator_version, 'resourcepools', id='resource_pool_create')
@kopf.on.resume(operator_domain, operator_version, 'resourcepools', id='resource_pool_resume')
@kopf.on.update(operator_domain, operator_version, 'resourcepools', id='resource_pool_update')
async def resource_pool_event(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    resource_pool = await ResourcePool.register(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_pool.manage(logger=logger)


@kopf.on.delete(operator_domain, operator_version, 'resourcepools')
async def resource_pool_delete(
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.ObjectLogger,
    meta: kopf.Meta,
    name: str,
    namespace: str,
    spec: kopf.Spec,
    status: kopf.Status,
    uid: str,
    **_
):
    await ResourcePool.unregister(name)
    resource_pool = ResourcePool(
        annotations = annotations,
        labels = labels,
        meta = meta,
        name = name,
        namespace = namespace,
        spec = spec,
        status = status,
        uid = uid,
    )
    await resource_pool.handle_delete(logger=logger)


@kopf.on.event(operator_domain, operator_version, 'resourceproviders')
async def resource_provider_event(event: Mapping, logger: kopf.ObjectLogger, **_) -> None:
    definition = event['object']
    if event['type'] == 'DELETED':
        await ResourceProvider.unregister(name=definition['metadata']['name'], logger=logger)
    else:
        await ResourceProvider.register(definition=definition, logger=logger)
