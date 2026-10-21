	.file	"accessors.cpp"
	.text
	.p2align 4
	.globl	read_current
	.type	read_current, @function
read_current:
.LFB10550:
	.cfi_startproc
	endbr64
	movsd	640(%rdi), %xmm0
	ret
	.cfi_endproc
.LFE10550:
	.size	read_current, .-read_current
	.p2align 4
	.globl	read_thrust
	.type	read_thrust, @function
read_thrust:
.LFB10551:
	.cfi_startproc
	endbr64
	movsd	576(%rdi), %xmm0
	ret
	.cfi_endproc
.LFE10551:
	.size	read_thrust, .-read_thrust
	.p2align 4
	.globl	read_torque
	.type	read_torque, @function
read_torque:
.LFB10552:
	.cfi_startproc
	endbr64
	movsd	584(%rdi), %xmm0
	ret
	.cfi_endproc
.LFE10552:
	.size	read_torque, .-read_torque
	.hidden	qt_version_tag_use
	.weak	qt_version_tag_use
	.section	.qtversion,"awG",@progbits,qt_version_tag_use,comdat
	.align 16
	.type	qt_version_tag_use, @gnu_unique_object
	.size	qt_version_tag_use, 16
qt_version_tag_use:
	.quad	qt_version_tag
	.quad	394499
	.ident	"GCC: (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0"
	.section	.note.GNU-stack,"",@progbits
	.section	.note.gnu.property,"a"
	.align 8
	.long	1f - 0f
	.long	4f - 1f
	.long	5
0:
	.string	"GNU"
1:
	.align 8
	.long	0xc0000002
	.long	3f - 2f
2:
	.long	0x3
3:
	.align 8
4:
